"""Look up scene-analysis chunk context for a list of timestamps."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChunkContext:
    """The slice of scene-analysis context covering a given timestamp."""

    timestamp_sec: float
    chunk_index: Optional[int]
    start_time: Optional[float]
    end_time: Optional[float]
    raw_text: str  # Free-text or stringified analysis
    chirp_transcription: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def _stringify_result_data(result_data: Dict[str, Any]) -> str:
    """Pull the most readable text out of a stored scene result."""
    if not result_data:
        return ""
    if "raw_text" in result_data and result_data["raw_text"]:
        return str(result_data["raw_text"])
    if "raw_response" in result_data and result_data["raw_response"]:
        return str(result_data["raw_response"])
    # Structured output — drop token usage / metadata, keep the analysis fields
    skip = {
        "token_usage",
        "finish_reason",
        "is_truncated",
        "continuation_count",
        "chunk_index",
        "chunk_duration",
        "gcs_path",
        "chirp_transcription",
    }
    keep = {k: v for k, v in result_data.items() if k not in skip}
    if not keep:
        return ""
    import json

    try:
        return json.dumps(keep, default=str, indent=2)
    except Exception:
        return str(keep)


def fetch_chunks_at(
    db,
    scene_job_id: str,
    timestamps: List[float],
) -> Dict[float, ChunkContext]:
    """Return per-timestamp chunk context drawn from a completed scene job.

    Looks up the scene job's video_id, reads its manifest (for chunk start/end
    times), then maps each timestamp to the chunk covering it and fetches that
    chunk's stored scene_result.
    """
    job = db.get_scene_job(scene_job_id)
    if not job:
        raise ValueError(f"Scene job not found: {scene_job_id}")

    video_id = job["video_id"]
    manifest = db.get_manifest(video_id) or {}
    chunks_meta = manifest.get("chunks") or []

    # Index chunks by their integer index for O(1) lookup
    chunks_by_index = {c["index"]: c for c in chunks_meta if "index" in c}

    # Pull all results for this scene job once
    all_results = db.get_results_for_job(scene_job_id) or []
    results_by_chunk: Dict[int, Dict[str, Any]] = {}
    for res in all_results:
        result_data = res.get("result_data") or {}
        ci = result_data.get("chunk_index")
        if ci is None:
            continue
        # Prefer the latest if multiple — but typically one per chunk
        results_by_chunk[ci] = res

    out: Dict[float, ChunkContext] = {}
    for ts in timestamps:
        chunk_index = _find_chunk_for_timestamp(ts, chunks_meta)
        chunk_meta = chunks_by_index.get(chunk_index) if chunk_index is not None else None
        result = results_by_chunk.get(chunk_index) if chunk_index is not None else None
        result_data = (result or {}).get("result_data") or {}

        out[ts] = ChunkContext(
            timestamp_sec=ts,
            chunk_index=chunk_index,
            start_time=(chunk_meta or {}).get("start_time"),
            end_time=(chunk_meta or {}).get("end_time"),
            raw_text=_stringify_result_data(result_data),
            chirp_transcription=result_data.get("chirp_transcription"),
            extra={"prompt_type": result_data.get("prompt_type")},
        )

    return out


def _find_chunk_for_timestamp(ts: float, chunks: List[Dict[str, Any]]) -> Optional[int]:
    """Return the index of the chunk covering ts, or the closest chunk if past the end."""
    if not chunks:
        return None

    # Most chunks have explicit start_time/end_time (Transcoder-built path).
    # Single-chunk fallback (no chunking) has duration only.
    for c in chunks:
        start = c.get("start_time")
        end = c.get("end_time")
        if start is None or end is None:
            # Single-chunk fallback path — covers everything
            return c.get("index", 0)
        if start <= ts < end:
            return c["index"]

    # ts is past the last chunk's end — clamp to the last chunk
    last = chunks[-1]
    return last.get("index")
