"""``asr`` stage: transcribe the commentary and extract scoring cues.

The play-by-play commentary is a semantic signal the pixels do not carry: it
names the scorer, calls the shot type ("for three"), and — uniquely — calls
*misses* ("no good"), which leave no score-bug delta. This stage transcribes
the mono broadcast audio with Whisper (``small.en`` on CPU) and tags cue
phrases with timestamps. Fusion (``timeline.fuse_signals``) owns using them:
cross-validating the scorer graphic's name against the spoken name, and
corroborating outcome / shot type. Commentary lags the play by 1-3 s, so ASR
owns *meaning*, never the timestamp.

Graceful degradation: if ``faster-whisper`` is not installed the stage writes a
skipped marker and the pipeline continues without it (jersey still comes from
the scorer graphic).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

MODEL = "small.en"  # tiny.en mangles names ("KJ Adams" -> "P.J. Adams"); small.en is clean on CPU

# Cue phrases, matched case-insensitively against the transcript. Kept small and
# high-precision — a cue is corroboration, never the sole basis for an event.
_CUE_PATTERNS: List[Tuple[str, str]] = [
    ("three", r"\bfor three\b|\bthree[- ]?pointer\b|\bfrom (?:downtown|deep|way)\b|\btriple\b"),
    ("free_throw", r"\bfree throw\b|\bfrom the (?:line|charity stripe)\b|\band (?:the |one)\b|and-?one\b"),
    # "good" is guarded so "no good" is a miss, not a make.
    (
        "make",
        r"\b(?:bucket|scores|count it|got it|and the foul|knocks it down|buries|lays it in|nails)\b|(?<!no )\bgood\b",
    ),
    (
        "miss",
        r"\bno good\b|\bmisses?\b|\boff the (?:rim|iron|mark|back)\b|\bin and out\b|\brims? out\b"
        r"|\bcan'?t (?:convert|get it to (?:go|fall))\b",
    ),
]
_CUE_RES = [(kind, re.compile(pat, re.IGNORECASE)) for kind, pat in _CUE_PATTERNS]


def extract_cues(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scoring-cue phrases with timestamps from transcript segments.

    Each cue is ``{t, kind, phrase}`` where ``kind`` is one of three/free_throw/
    make/miss. A segment can raise several cues (e.g. "for three, and it's good").
    """
    cues: List[Dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text", ""))
        t = round(float(seg.get("t_start", seg.get("t", 0.0))), 3)
        for kind, rex in _CUE_RES:
            m = rex.search(text)
            if m:
                cues.append({"t": t, "kind": kind, "phrase": m.group(0).strip().lower()})
    return cues


def transcribe(clip_path: Any, model_name: str = MODEL) -> List[Dict[str, Any]]:
    """Whisper transcript as ``[{t_start, t_end, text}]`` (raises if deps absent)."""
    from faster_whisper import WhisperModel  # optional heavy dep — import lazily

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(clip_path), beam_size=5, language="en")
    return [
        {"t_start": round(float(s.start), 3), "t_end": round(float(s.end), 3), "text": s.text.strip()} for s in segments
    ]


def _has_audio(clip_path: Any) -> bool:
    """True if the clip carries an audio stream (skip Whisper entirely if not)."""
    import av

    try:
        container = av.open(str(clip_path))
        try:
            return bool(container.streams.audio)
        finally:
            container.close()
    except Exception:  # noqa: BLE001 — probe is advisory
        return False


def run_stage(ctx: Any) -> None:  # ctx: libs.basketball.stages.StageContext
    """``asr`` stage: transcribe commentary + tag scoring cues (or skip)."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    def _skip(reason: str) -> None:
        logger.warning("asr: skipping ASR for clip %s (%s)", ctx.clip_id, reason)
        ctx.cache.write_json(ctx.stage, {"clip_id": ctx.clip_id, "skipped": True, "reason": reason})

    if not _has_audio(ctx.clip_path):
        _skip("no audio stream")
        return
    try:
        segments = transcribe(ctx.clip_path)
    except ImportError:
        _skip("faster-whisper not installed")
        return
    except Exception as exc:  # noqa: BLE001 — a transcription failure must not break the pipeline
        _skip(f"transcription failed: {exc}")
        return
    cues = extract_cues(segments)
    logger.info("asr: %d segment(s), %d cue(s) for clip %s", len(segments), len(cues), ctx.clip_id)
    ctx.cache.write_json(
        ctx.stage,
        {"clip_id": ctx.clip_id, "model": MODEL, "segments": segments, "cues": cues},
    )
