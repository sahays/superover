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
from libs.engagement.prompts import (
    ENGAGEMENT_RESPONSE_SCHEMA,
    RECOMMENDATIONS_PROMPT_TEXT,
    RECOMMENDATIONS_RESPONSE_SCHEMA,
)
from libs.engagement.recommendations import RecommendationStats
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

    def recommend(self, stats: RecommendationStats, cues_by_minute: Dict[int, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Synthesize prescriptive recommendations grounded in the supplied stats.

        `stats` is the deterministic bundle from `compute_stats(...)`.
        `cues_by_minute` maps minute_index → list of cues spanning that minute,
        used so the LLM can describe what was on-screen during low/high minutes.
        """
        sections: List[str] = [RECOMMENDATIONS_PROMPT_TEXT, "", "# Stats"]
        sections.append(f"overall_avg = {stats.overall_avg:.4f}\ntarget_avg = {stats.target_avg:.4f}")

        sections.append("\n## Top positive entities (do_more_of candidates)")
        for d in stats.top_positive_entities:
            sections.append(_format_delta(d))
        if not stats.top_positive_entities:
            sections.append("(none)")

        sections.append("\n## Top negative entities (do_less_of candidates)")
        for d in stats.top_negative_entities:
            sections.append(_format_delta(d))
        if not stats.top_negative_entities:
            sections.append("(none)")

        sections.append("\n## High-engagement minute buckets (positive examples)")
        for m in stats.high_minutes:
            sections.append(_format_minute(m, cues_by_minute.get(m.minute_index, [])))

        sections.append("\n## Low-engagement minute buckets (per_minute_callouts candidates)")
        for m in stats.low_minutes:
            sections.append(_format_minute(m, cues_by_minute.get(m.minute_index, [])))

        full_prompt = "\n".join(sections)
        logger.info(
            f"[ENGAGEMENT] Recommendation call: {len(stats.top_positive_entities)} +entities, "
            f"{len(stats.top_negative_entities)} -entities, "
            f"{len(stats.high_minutes)} high-minutes, {len(stats.low_minutes)} low-minutes"
        )

        config = types.GenerateContentConfig(
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_default_output_tokens,
            response_mime_type="application/json",
            response_schema=RECOMMENDATIONS_RESPONSE_SCHEMA,
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
            raise RuntimeError(f"Recommendations call blocked by Gemini (reason: {finish_reason})")

        finish_reason = str(response.candidates[0].finish_reason)
        try:
            parsed = json.loads(response.text)
        except Exception as e:
            raise RuntimeError(f"Failed to parse recommendations as JSON: {e}\n{response.text[:400]}")

        token_usage: Dict[str, Any] = {}
        if response.usage_metadata:
            token_usage = calculate_cost(response.usage_metadata, settings.gemini_default_model)

        return {
            "headline": parsed.get("headline", ""),
            "do_more_of": parsed.get("do_more_of", []),
            "do_less_of": parsed.get("do_less_of", []),
            "per_minute_callouts": parsed.get("per_minute_callouts", []),
            "finish_reason": finish_reason,
            "token_usage": token_usage,
        }


def _format_delta(d) -> str:
    return (
        f"- {d.name} ({d.kind}): delta_pct={d.delta_pct:+.1f}%, "
        f"avg_during={d.avg_during:.3f} vs overall {d.avg_overall:.3f}, "
        f"sample_size={d.sample_size}, coverage={d.coverage_sec:.0f}s"
    )


def _format_minute(m, cues: List[Dict[str, Any]]) -> str:
    cue_lines = []
    for c in cues[:6]:  # cap for token budget
        speaker = c.get("speaker") or ""
        prefix = f"{speaker}: " if speaker else ""
        cue_lines.append(f"  - [{c['start_sec']:.1f}-{c['end_sec']:.1f}] {prefix}{c['text']}")
    cue_block = "\n".join(cue_lines) if cue_lines else "  (no cues in this minute)"
    return (
        f"- minute {m.minute_index} ({m.minute_start_sec:.0f}-{m.minute_end_sec:.0f}s) "
        f"avg={m.avg_score:.3f}\n{cue_block}"
    )


_engagement_analyzer: EngagementAnalyzer | None = None


@lru_cache()
def get_engagement_analyzer() -> EngagementAnalyzer:
    """Singleton EngagementAnalyzer."""
    global _engagement_analyzer
    if _engagement_analyzer is None:
        _engagement_analyzer = EngagementAnalyzer()
    return _engagement_analyzer
