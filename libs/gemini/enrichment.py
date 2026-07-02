"""Sync-time content enrichment for the search index.

Scene analyses label people by their on-screen character ("Sonu"), not the
actor — so actor-name queries ("Sunil Grover shows") can't match on text and
ride entirely on the embedding model's fuzzy associations. This enricher
makes one Gemini Flash call per video at sync time (off the search hot path)
to produce a short blurb naming the canonical title and its known lead cast,
which gets appended to the embedding text of the video's rows.
"""

import json
import logging
from functools import lru_cache
from typing import Optional

from google import genai
from google.genai import types

from config import settings
from libs.gemini.common import model_name, retry_with_backoff

logger = logging.getLogger(__name__)

ENRICHMENT_SYSTEM_PROMPT = """\
You identify film/TV content from a video filename and an analysis summary.
Output a single short line for search indexing:
"Title: <canonical title>. Cast: <actor 1>, <actor 2>, ...".

Rules:
- Name the show/film's canonical title if the filename/summary identifies it.
- List lead actors ONLY if you are confident they belong to THIS title.
  Never guess — a wrong actor name poisons search. Omit the Cast part
  entirely when unsure.
- If you cannot identify the content at all, return an empty blurb.
- No commentary, no extra fields.
"""

RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "blurb": types.Schema(
            type=types.Type.STRING,
            description="'Title: ... Cast: ...' line, or empty if unidentifiable",
        ),
    },
    required=["blurb"],
)


class ContentEnricher:
    """Generates title/cast blurbs for search-index enrichment."""

    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = model_name(settings.gemini_search_model)

    def enrich(self, video_filename: Optional[str], summary: Optional[str], genre: Optional[str] = None) -> str:
        """Return a 'Title: … Cast: …' blurb, or '' when unidentifiable/failed."""
        if not video_filename and not summary:
            return ""
        prompt = (
            f"Filename: {video_filename or '(unknown)'}\n"
            f"Genre: {genre or '(unknown)'}\n"
            f"Summary: {(summary or '')[:500]}"
        )
        try:
            response = retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=ENRICHMENT_SYSTEM_PROMPT,
                    max_output_tokens=256,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                ),
            )
            blurb = json.loads(response.text).get("blurb", "").strip()
            logger.info(f"Enrichment for {video_filename!r}: {blurb!r}")
            return blurb
        except Exception as e:
            logger.warning(f"Enrichment failed for {video_filename!r}: {e}")
            return ""


@lru_cache(maxsize=1)
def get_content_enricher() -> ContentEnricher:
    """Get cached content enricher singleton."""
    return ContentEnricher()
