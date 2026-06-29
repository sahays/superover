"""Gemini Search Curator — curates BQ search results into recommendations."""

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from config import settings
from libs.gemini.common import model_name, retry_with_backoff

logger = logging.getLogger(__name__)

CURATOR_SYSTEM_PROMPT = """\
You are a video content curator. Given a user's search query and a list of \
video analysis results from a semantic search, produce intelligent recommendations.

Match the user's intent against these fields in the analysis JSON:
- **Actors / people**: names, roles, descriptions of people visible on screen.
- **Genre & content type**: drama, comedy, documentary, sports, etc.
- **Mood / tone**: emotional feel — tense, joyful, melancholic, etc.
- **Scene summaries**: narrative descriptions of what happens in each scene.
- **Objects & visuals**: notable objects, vehicles, props, animals, text on screen.
- **Key events / actions**: fights, celebrations, conversations, stunts, reveals.
- **Timeline timestamps**: use scene-level timestamp_start / timestamp_end from \
the analysis to locate specific moments.

Recommendation rules:
- Be generous and inclusive. Recommend every result with a plausible connection \
to the query — partial, thematic, or loose matches all count. Prefer including a \
result over dropping it; the user would rather see a few extra options than none.
- Return up to 5 recommendations, ranked best-first.
- Prefer clip recommendations when the match is a specific moment rather than \
the whole video. Use each result's timestamp_start / timestamp_end (the matched \
moment's window) for clip_start / clip_end (format HH:MM:SS).
- For full video recommendations, omit clip_start / clip_end.
- Confidence scoring (0.0–1.0): 0.80+ = strong, 0.50–0.79 = solid, \
0.30–0.49 = loose/thematic (still include it), below 0.30 = do not include.
- Order recommendations by relevance (highest confidence first).
- Only return an empty list if truly nothing in the results relates to the query.

Keep output tight (latency matters):
- Each `reason`: one short phrase, max ~12 words. No full sentences.
- `response_text`: a single short sentence.
"""

RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "response_text": types.Schema(
            type=types.Type.STRING,
            description="One short sentence summarizing the findings",
        ),
        "recommendations": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    # Only fields the MODEL must decide are generated. Identifiers
                    # we already have (video_filename, gcs_path) are filled in
                    # server-side from the BQ row by video_id — keeping them out
                    # of the output shrinks tokens (gcs_path is a long URL) and
                    # avoids the model mangling them.
                    "video_id": types.Schema(type=types.Type.STRING),
                    "recommendation_type": types.Schema(
                        type=types.Type.STRING,
                        description="full_video or clip",
                    ),
                    "title": types.Schema(
                        type=types.Type.STRING,
                        description="Short title for the recommendation",
                    ),
                    "reason": types.Schema(
                        type=types.Type.STRING,
                        description="One short phrase (max ~12 words) on why it fits",
                    ),
                    "clip_start": types.Schema(
                        type=types.Type.STRING,
                        description="HH:MM:SS start time for clips",
                    ),
                    "clip_end": types.Schema(
                        type=types.Type.STRING,
                        description="HH:MM:SS end time for clips",
                    ),
                    "confidence": types.Schema(
                        type=types.Type.NUMBER,
                        description="0-1 confidence score",
                    ),
                },
                required=[
                    "video_id",
                    "recommendation_type",
                    "title",
                    "reason",
                    "confidence",
                ],
            ),
        ),
    },
    required=["response_text", "recommendations"],
)


# Cap the rows handed to the model. BQ returns up to 20 (often many chunks of the
# same video); the curator only needs the closest handful per distinct video to
# pick a few recommendations. Fewer rows = smaller prompt = lower latency.
CURATOR_MAX_RESULTS = 6


def _compact_analysis(rd: dict) -> dict:
    """Project a scene-analysis result_data to only the fields the curator reasons
    over (classification, mood, setting, actors, a couple of scene summaries).

    Drops the heavy payload — dialogue, detailed descriptions, cues, events,
    emotions, segments, notable observations — that bloats the prompt and
    dominates curation latency.
    """
    out: dict[str, Any] = {}
    for k in ("genre", "type", "content_type"):
        v = rd.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    summary = rd.get("chunk_summary")
    if isinstance(summary, str) and summary.strip():
        out["summary"] = summary.strip()

    scenes = rd.get("scenes")
    if isinstance(scenes, list) and scenes:
        first = scenes[0] if isinstance(scenes[0], dict) else {}
        mood = first.get("mood") if isinstance(first.get("mood"), dict) else {}
        tone, energy = (mood or {}).get("tone", ""), (mood or {}).get("energy", "")
        if tone or energy:
            out["mood"] = f"{tone} {energy}".strip()
        setting = first.get("setting") if isinstance(first.get("setting"), dict) else {}
        location = (setting or {}).get("location")
        if location:
            out["setting"] = location

        actors: list[str] = []
        seen: set[str] = set()
        scene_summaries: list[str] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            ss = scene.get("summary")
            if isinstance(ss, str) and ss.strip():
                scene_summaries.append(ss.strip())
            for person in scene.get("people", []) or []:
                if isinstance(person, dict):
                    name = person.get("label", "")
                    if name and name not in seen and not name.startswith("Person"):
                        seen.add(name)
                        actors.append(name)
        if actors:
            out["actors"] = actors[:6]
        if scene_summaries:
            out["scene_summaries"] = scene_summaries[:2]

    return out


def _compact_entry(row: dict) -> dict:
    """Build one compact context entry from a BQ result row."""
    entry: dict[str, Any] = {
        "video_id": row.get("video_id", ""),
        "video_filename": row.get("video_filename", ""),
        "gcs_path": row.get("gcs_path", ""),
        "timestamp_start": row.get("timestamp_start"),
        "timestamp_end": row.get("timestamp_end"),
    }
    rd = row.get("result_data_json")
    if isinstance(rd, str):
        try:
            rd = json.loads(rd)
        except (json.JSONDecodeError, ValueError):
            rd = None
    if isinstance(rd, dict):
        entry["analysis"] = _compact_analysis(rd)
    else:
        entry["text_content"] = (row.get("text_content") or "")[:400]
    return entry


def _compact_results(bq_results: list[dict], limit: int) -> list[dict]:
    """Dedupe to the closest chunk per video, cap to `limit`, and compact each.

    `bq_results` is already sorted by distance ascending, so the first row seen
    for a video is its best match.
    """
    best_by_video: dict[str, dict] = {}
    for row in bq_results:
        vid = row.get("video_id", "")
        if vid not in best_by_video:
            best_by_video[vid] = row
    return [_compact_entry(row) for row in list(best_by_video.values())[:limit]]


class SearchCurator:
    """Curates BigQuery search results using Gemini for intelligent recommendations."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = model_name(settings.gemini_search_model)
        self.max_retries = max_retries
        self.base_delay = base_delay

    def curate_search_results(self, query: str, bq_results: list[dict]) -> dict[str, Any]:
        """Curate BQ search results into structured recommendations.

        Returns dict with response_text and recommendations list.
        On failure, returns a fallback with raw results.
        """
        if not bq_results:
            return {
                "response_text": "No results found for your search query.",
                "recommendations": [],
            }

        # Build a compact, token-light context: dedupe to best chunk per video,
        # cap rows, and keep only the fields the curator reasons over.
        results_context = _compact_results(bq_results, CURATOR_MAX_RESULTS)

        user_prompt = (
            f"Search query: {query}\n\n"
            f"Search results ({len(results_context)} matches):\n"
            f"{json.dumps(results_context, separators=(',', ':'))}"
        )
        logger.info("Curator context: %d videos, %d chars", len(results_context), len(user_prompt))

        try:
            response = retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURATOR_SYSTEM_PROMPT,
                    max_output_tokens=settings.gemini_search_output_tokens,
                    temperature=settings.gemini_temperature,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    thinking_config=types.ThinkingConfig(
                        # gemini-3.5-flash is Gemini 3: reasoning is controlled by
                        # thinking_level (not thinking_budget). MINIMAL is the lowest
                        # setting — keeps curation fast while restoring LLM ranking.
                        thinking_level=types.ThinkingLevel.MINIMAL,
                    ),
                ),
            )

            result = json.loads(response.text)
            logger.info(
                f"Search curation complete: {len(result.get('recommendations', []))} "
                f"recommendations for query '{query}'"
            )
            return result

        except Exception as e:
            logger.error(f"Search curation failed: {e}", exc_info=True)
            return self._fallback_response(query, bq_results)

    def _fallback_response(self, query: str, bq_results: list[dict]) -> dict[str, Any]:
        """Generate a basic fallback when Gemini curation fails."""
        recommendations = []
        for row in bq_results[:10]:
            recommendations.append(
                {
                    "video_id": row.get("video_id", ""),
                    "video_filename": row.get("video_filename", ""),
                    "gcs_path": row.get("gcs_path", ""),
                    "recommendation_type": "full_video",
                    "title": row.get("video_filename", "Untitled"),
                    "reason": f"Matched search query with distance {row.get('distance', 0):.3f}",
                    "confidence": max(0, 1 - row.get("distance", 1)),
                }
            )
        return {
            "response_text": (
                f'Found {len(bq_results)} result(s) matching "{query}". Showing raw results (AI curation unavailable).'
            ),
            "recommendations": recommendations,
        }
