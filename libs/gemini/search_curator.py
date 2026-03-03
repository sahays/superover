"""Gemini Search Curator — curates BQ search results into recommendations."""

import json
import logging
import time
from typing import Any

from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from config import settings

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
- Only recommend results that genuinely match the query intent.
- Prefer clip recommendations when the match is a specific moment rather than \
the whole video. Extract clip_start and clip_end from the scene-level timestamps \
in the analysis JSON (format HH:MM:SS).
- For full video recommendations, omit clip_start / clip_end.
- Confidence scoring (0.0–1.0): 0.85+ = strong match on multiple fields, \
0.60–0.84 = partial match, below 0.60 = do not include.
- Order recommendations by relevance (highest confidence first).
- Write a concise, natural language response_text summarizing what you found.
- If nothing is relevant, return an empty recommendations list with a helpful \
response_text.
"""

RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "response_text": types.Schema(
            type=types.Type.STRING,
            description="Natural language summary of findings",
        ),
        "recommendations": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "video_id": types.Schema(type=types.Type.STRING),
                    "video_filename": types.Schema(type=types.Type.STRING),
                    "gcs_path": types.Schema(type=types.Type.STRING),
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
                        description="Why this is recommended",
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
                    "video_filename",
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


def _model_name(name: str) -> str:
    """Strip 'models/' prefix if present."""
    return name.removeprefix("models/")


class SearchCurator:
    """Curates BigQuery search results using Gemini for intelligent recommendations."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = _model_name(settings.gemini_search_model)
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute a function with exponential backoff retry logic."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ServiceUnavailable,
            ) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} retry attempts failed")
            except Exception as e:
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                raise

        raise last_exception

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

        # Build context for Gemini from BQ results
        results_context = []
        for row in bq_results:
            entry: dict[str, Any] = {
                "video_id": row.get("video_id", ""),
                "video_filename": row.get("video_filename", ""),
                "gcs_path": row.get("gcs_path", ""),
                "distance": row.get("distance", 0),
                "timestamp_start": row.get("timestamp_start"),
                "timestamp_end": row.get("timestamp_end"),
            }
            # Include full analysis JSON if available
            result_data_json = row.get("result_data_json")
            if result_data_json:
                entry["analysis"] = result_data_json
            else:
                entry["text_content"] = row.get("text_content", "")
            results_context.append(entry)

        user_prompt = (
            f"Search query: {query}\n\n"
            f"Search results ({len(results_context)} matches):\n"
            f"{json.dumps(results_context, indent=2)}"
        )

        try:
            response = self._retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURATOR_SYSTEM_PROMPT,
                    max_output_tokens=settings.gemini_search_output_tokens,
                    temperature=0.3,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=0,
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
