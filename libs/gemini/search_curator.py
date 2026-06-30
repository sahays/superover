"""Gemini Search Curator — curates BQ search results into recommendations."""

import json
import logging
from typing import Any, Optional

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
- **Scenes & timestamps**: each result's analysis has a `scenes` list; every scene \
carries `start`, `end` (HH:MM:SS), a `summary`, and the key `people` on screen. Use \
these to locate the specific moment the query is about.

Recommendation rules:
- Be generous and inclusive. Recommend every result with a plausible connection \
to the query — partial, thematic, or loose matches all count. Prefer including a \
result over dropping it; the user would rather see a few extra options than none.
- Return up to 5 recommendations, ranked best-first.
- Prefer a `clip` recommendation whenever the query targets a specific moment, \
person, action, or visual (e.g. "Kiara Advani in a pink sari"). Find the scene in \
that result's `scenes` list whose `summary`/`people` best matches, and set \
clip_start / clip_end to that scene's `start` / `end` (format HH:MM:SS). When several \
adjacent scenes match, span from the first match's `start` to the last match's `end`.
- Use `full_video` only when the whole video is the best answer, or when no single \
scene matches better than the video as a whole. For full_video, omit clip_start / clip_end.
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


def _clip_time(t: Any) -> Optional[str]:
    """Normalize a scene time like '00:00:07.200' to 'HH:MM:SS' (drop millis)."""
    if not isinstance(t, str) or not t.strip():
        return None
    return t.strip().split(".")[0]


def _sec_to_hhmmss(s: Any) -> Optional[str]:
    """Convert a numeric second offset (e.g. 44.0) to 'HH:MM:SS'."""
    try:
        total = int(float(s))
    except (TypeError, ValueError):
        return None
    if total < 0:
        return None
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _scenes_from_scene_schema(scenes: list, out: dict, actors: list, seen: set) -> list:
    """Scene-schema analysis: scenes[] with start_time/end_time + summary + people."""
    first = scenes[0] if isinstance(scenes[0], dict) else {}
    mood = first.get("mood") if isinstance(first.get("mood"), dict) else {}
    tone, energy = (mood or {}).get("tone", ""), (mood or {}).get("energy", "")
    if tone or energy:
        out["mood"] = f"{tone} {energy}".strip()
    setting = first.get("setting") if isinstance(first.get("setting"), dict) else {}
    location = (setting or {}).get("location")
    if location:
        out["setting"] = location

    scene_entries: list[dict[str, Any]] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        # Named people on screen in this scene (skip generic "Person N" labels).
        scene_people: list[str] = []
        for person in scene.get("people", []) or []:
            if isinstance(person, dict):
                name = person.get("label", "")
                if name and not name.startswith("Person"):
                    scene_people.append(name)
                    if name not in seen:
                        seen.add(name)
                        actors.append(name)

        ss = scene.get("summary")
        if not (isinstance(ss, str) and ss.strip()):
            continue
        entry: dict[str, Any] = {"summary": ss.strip()[:200]}
        start, end = _clip_time(scene.get("start_time")), _clip_time(scene.get("end_time"))
        if start:
            entry["start"] = start
        if end:
            entry["end"] = end
        if scene_people:
            entry["people"] = scene_people[:4]
        scene_entries.append(entry)
    return scene_entries


def _scenes_from_event_schema(rd: dict, events: list, actors: list, seen: set) -> list:
    """Event-schema analysis: events[] with start_sec/end_sec + description + tag.

    Projected into the same clip-able shape the curator reads. Actor names come
    from the entities[] character list rather than per-scene people.
    """
    scene_entries: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        desc = ev.get("description")
        if not (isinstance(desc, str) and desc.strip()):
            continue
        entry: dict[str, Any] = {"summary": desc.strip()[:200]}
        start, end = _sec_to_hhmmss(ev.get("start_sec")), _sec_to_hhmmss(ev.get("end_sec"))
        if start:
            entry["start"] = start
        if end:
            entry["end"] = end
        tag = ev.get("tag")
        if isinstance(tag, str) and tag.strip():
            entry["tag"] = tag.strip()
        scene_entries.append(entry)

    for ent in rd.get("entities") or []:
        if isinstance(ent, dict) and ent.get("kind") == "character":
            name = ent.get("name")
            if isinstance(name, str) and name.strip() and name not in seen:
                seen.add(name)
                actors.append(name.strip())
    return scene_entries


def _compact_analysis(rd: dict) -> dict:
    """Project a scene-analysis result_data to only the fields the curator reasons
    over (classification, mood, setting, actors, and per-scene start/end/summary).

    Handles BOTH analysis schemas, projecting each into a unified `scenes` list
    of {start, end, summary, ...} so the curator can return clip recommendations:
      - scene schema: `scenes[]` with start_time/end_time (HH:MM:SS).
      - event schema: `events[]` with start_sec/end_sec (numeric) + description.
    Chunking is no longer used, so all times are absolute video time.

    Drops the heavy payload — dialogue, detailed descriptions, cues, raw
    entities, emotions, segments — that bloats the prompt and dominates latency.
    """
    out: dict[str, Any] = {}
    for k in ("genre", "type", "content_type"):
        v = rd.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    # Overall summary: scene schema uses `chunk_summary`, event schema uses `summary`.
    summary = rd.get("chunk_summary") or rd.get("summary")
    if isinstance(summary, str) and summary.strip():
        out["summary"] = summary.strip()

    actors: list[str] = []
    seen: set[str] = set()
    scenes, events = rd.get("scenes"), rd.get("events")
    if isinstance(scenes, list) and scenes:
        scene_entries = _scenes_from_scene_schema(scenes, out, actors, seen)
    elif isinstance(events, list) and events:
        scene_entries = _scenes_from_event_schema(rd, events, actors, seen)
    else:
        scene_entries = []

    if actors:
        out["actors"] = actors[:6]
    if scene_entries:
        # Cap scene count to bound prompt size / curation latency.
        out["scenes"] = scene_entries[:12]

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
