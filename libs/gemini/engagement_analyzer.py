"""
Gemini Engagement Analyzer
Combines BARC peaks/valleys with scene-analysis context and produces structured
explanations of why each moment is a high or low point of audience engagement.
"""

import json
import logging
from functools import lru_cache
from typing import Any, Dict, List

from google import genai
from google.genai import types

from config import settings
from libs.engagement.peak_detection import Extremum
from libs.engagement.prompts import ENGAGEMENT_RESPONSE_SCHEMA
from libs.engagement.scene_context import ChunkContext
from libs.gemini.common import calculate_cost, model_name, retry_with_backoff

logger = logging.getLogger(__name__)


def _format_extremum(label: str, item: Extremum, ctx: ChunkContext) -> str:
    """Render one peak/valley + context block for the prompt."""
    range_part = ""
    if ctx.start_time is not None and ctx.end_time is not None:
        range_part = f" (chunk #{ctx.chunk_index}, covers {ctx.start_time:.1f}s–{ctx.end_time:.1f}s)"

    chirp_part = ""
    chirp = ctx.chirp_transcription or {}
    if chirp:
        ts_text = chirp.get("timestamps") or chirp.get("transcript") or ""
        if ts_text:
            chirp_part = f"\nDialog/transcript:\n{ts_text}\n"

    text = ctx.raw_text or "(no scene-analysis context available for this chunk)"
    return (
        f"=== {label} #{item.rank} — t={item.timestamp_sec:.1f}s, "
        f"score={item.score:g}{range_part} ===\n"
        f"Scene context:\n{text}\n"
        f"{chirp_part}"
    )


class EngagementAnalyzer:
    """Single Gemini call that explains a batch of peaks/valleys."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = model_name(settings.gemini_default_model)
        self.max_retries = max_retries
        self.base_delay = base_delay

    def explain(
        self,
        prompt_text: str,
        peaks: List[Extremum],
        valleys: List[Extremum],
        contexts: Dict[float, ChunkContext],
    ) -> Dict[str, Any]:
        """Call Gemini once with all peaks + valleys + their scene contexts.

        Returns {"peaks": [...], "valleys": [...], "token_usage": {...}, "finish_reason": str}.
        """
        sections: List[str] = [prompt_text, ""]
        sections.append("# Top engagement moments\n")
        for p in peaks:
            sections.append(_format_extremum("PEAK", p, contexts[p.timestamp_sec]))
        sections.append("\n# Lowest engagement moments\n")
        for v in valleys:
            sections.append(_format_extremum("VALLEY", v, contexts[v.timestamp_sec]))
        full_prompt = "\n".join(sections)

        logger.info(
            f"[ENGAGEMENT] Calling {self.model_name} with {len(peaks)} peaks + "
            f"{len(valleys)} valleys ({len(full_prompt)} chars)"
        )

        config = types.GenerateContentConfig(
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_default_output_tokens,
            response_mime_type="application/json",
            response_schema=ENGAGEMENT_RESPONSE_SCHEMA,
        )

        response = retry_with_backoff(
            self.client.models.generate_content,
            model=self.model_name,
            contents=[full_prompt],
            config=config,
            max_retries=self.max_retries,
            base_delay=self.base_delay,
        )

        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
            raise RuntimeError(f"Engagement analysis blocked by Gemini (reason: {finish_reason})")

        finish_reason = str(response.candidates[0].finish_reason)
        try:
            parsed = json.loads(response.text)
        except Exception as e:
            raise RuntimeError(f"Failed to parse engagement response as JSON: {e}\n{response.text[:400]}")

        token_usage: Dict[str, Any] = {}
        if response.usage_metadata:
            token_usage = calculate_cost(response.usage_metadata, settings.gemini_default_model)

        return {
            "peaks": parsed.get("peaks", []),
            "valleys": parsed.get("valleys", []),
            "finish_reason": finish_reason,
            "token_usage": token_usage,
        }


_engagement_analyzer: EngagementAnalyzer | None = None


@lru_cache()
def get_engagement_analyzer() -> EngagementAnalyzer:
    """Singleton EngagementAnalyzer."""
    global _engagement_analyzer
    if _engagement_analyzer is None:
        _engagement_analyzer = EngagementAnalyzer()
    return _engagement_analyzer
