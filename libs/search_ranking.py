"""Deterministic ranking of vector-search rows into recommendations.

Replaces the curator LLM call on the search hot path (~2.4s median). The
vector store already returns rows sorted by cosine distance; this module
dedupes to the best chunk per video, gates cards behind a display distance
threshold (the curator used to drop off-topic rows — e.g. chitchat queries),
derives clip vs full_video from the chunk's timestamps, and maps distance to
a confidence score. Relevance narration is handled by the avatar Live model,
which receives the structured recommendation list and judges fit itself.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_RECOMMENDATIONS = 5

# Distances tighter than the threshold by this span map to confidence 1.0;
# at the threshold confidence bottoms out. Cosine-distance spreads are model
# dependent (text-embedding-005 clusters in 0.95–1.12), so the display
# threshold lives in config and this span just shapes the ramp within it.
CONFIDENCE_SPAN = 0.25
CONFIDENCE_FLOOR = 0.30


def _clip_time(t: Any) -> Optional[str]:
    """Normalize a chunk time like '00:00:07.200' to 'HH:MM:SS' (drop millis)."""
    if not isinstance(t, str) or not t.strip():
        return None
    return t.strip().split(".")[0]


def _prettify_filename(filename: Optional[str]) -> str:
    """Turn 'Sony_Liv-The_Hunt.mp4' into 'Sony Liv The Hunt' for card titles."""
    if not filename:
        return "Untitled"
    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    pretty = " ".join(stem.replace("_", " ").replace("-", " ").split())
    return pretty if any(c.isalnum() for c in pretty) else "Untitled"


def _confidence(distance: float, max_distance: float) -> float:
    """Linear ramp: distance == max_distance → floor, tighter → up to 1.0."""
    score = CONFIDENCE_FLOOR + (1.0 - CONFIDENCE_FLOOR) * (max_distance - distance) / CONFIDENCE_SPAN
    return round(max(CONFIDENCE_FLOOR, min(1.0, score)), 3)


def _reason(meta: dict) -> str:
    """Short phrase on why the video matched, from its analysis metadata."""
    parts: list[str] = []
    for key in ("genre", "content_type", "mood", "setting"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    actors = meta.get("actors")
    if isinstance(actors, list) and actors:
        parts.append("with " + ", ".join(actors[:3]))
    if parts:
        return "; ".join(parts)[:120]
    desc = meta.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()[:120]
    return "Close semantic match"


def rank_results(
    video_groups: dict[str, list[dict]],
    metadata_by_video: dict[str, dict],
    max_distance: float,
    limit: int = MAX_RECOMMENDATIONS,
) -> list[dict]:
    """Rank grouped vector-search rows into recommendation dicts.

    `video_groups` maps video_id -> rows sorted by distance ascending (the
    first row is the video's best match). Rows whose best distance exceeds
    `max_distance` produce no card — that gate is what keeps off-topic
    queries from surfacing junk now that no LLM filters the results.
    """
    candidates: list[tuple[float, str, dict]] = []
    for video_id, matches in video_groups.items():
        best = matches[0]
        distance = best.get("distance")
        if distance is None or distance >= max_distance:
            continue
        candidates.append((distance, video_id, best))
    candidates.sort(key=lambda c: c[0])

    recommendations = []
    for distance, video_id, best in candidates[:limit]:
        meta = metadata_by_video.get(video_id, {})
        clip_start = _clip_time(best.get("timestamp_start"))
        clip_end = _clip_time(best.get("timestamp_end"))
        is_clip = bool(clip_start and clip_end and clip_start != clip_end)
        recommendations.append(
            {
                "video_id": video_id,
                "video_filename": best.get("video_filename", ""),
                "gcs_path": best.get("gcs_path", ""),
                "recommendation_type": "clip" if is_clip else "full_video",
                "title": _prettify_filename(best.get("video_filename")),
                "reason": _reason(meta),
                "clip_start": clip_start if is_clip else None,
                "clip_end": clip_end if is_clip else None,
                "confidence": _confidence(distance, max_distance),
            }
        )

    logger.info(
        "Ranked %d video(s) into %d recommendation(s) (max_distance=%.3f)",
        len(video_groups),
        len(recommendations),
        max_distance,
    )
    return recommendations
