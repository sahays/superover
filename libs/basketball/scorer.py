"""``scorer`` stage: read the broadcast "scorer" lower-third graphic.

When the broadcast features a player after a scoring play it shows a lower-third
banner: ``<number> <NAME>  <n> PTS | <fg>``. OCR'ing the leading number gives
the scorer's jersey **directly** — with no shooter tracking — so it works even
when the make is scoreboard-only (the trajectory missed the shot, which is the
common case and the reason jersey attribution via the shooter track fails).

The featured name is a person, never a team, which separates a real scorer
graphic from the score bug's ranked-team label ("(4) KANSAS" OCR's as the token
"4KANSAS"): a name that maps to a known team is dropped.

This is a signal that reads on-screen text; fusion (``timeline.fuse_signals``)
owns attaching the number to a scoreboard-confirmed make by time.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from libs.basketball import video
from libs.basketball.scorebug import map_abbr_to_team, normalize_abbr

logger = logging.getLogger(__name__)

SAMPLE_FPS = 2.0  # the graphic lingers for seconds — 2 fps is plenty and cheap
BAND_TOP_FRAC = 0.80  # OCR the bottom fifth of the frame (where lower-thirds live)
UPSCALE = 1.5
MIN_READ_CONF = 0.6  # OCR reads below this are ignored
MIN_NAME_LEN = 5  # a scorer name is a person (>= 5 letters), not "ST" or "PTS"
MAX_NAME_LEN = 16  # ... and a person, not a caption ("21ST SEASON AS ... COACH")
MIN_FRAMES = 3  # the graphic must persist a few reads to count (not a flicker)
MERGE_GAP_SEC = 3.0  # same-number detections within this gap are one feature

# "<1-2 digit number><CAPS NAME>" — RapidOCR usually drops the interior spaces,
# so "24 ARTHUR KALUMA" arrives as the token "24ARTHURKALUMA". Prefix match (no
# end anchor) tolerates a trailing stat blob if the OCR merges one in.
_SCORER_RE = re.compile(r"^(\d{1,2})([A-Z][A-Z'.\-]{%d,})" % (MIN_NAME_LEN - 1))


def parse_scorer_token(text: str) -> Optional[Tuple[str, str]]:
    """A lower-third OCR token -> (jersey_number, NAME) if it is a scorer graphic.

    Returns None for anything that is not a ``<number><person-name>`` — including
    the score bug's ranked-team label, since a name that maps to a known team
    (``KANSAS``, ``KANSASST``) is a team, not a scorer.
    """
    s = "".join(str(text).split()).upper()
    m = _SCORER_RE.match(s)
    if not m:
        return None
    number, name = m.group(1), m.group(2)
    if len(name) > MAX_NAME_LEN:
        return None  # a caption ("21STSEASONASKANSASHEADCOACH"), not a scorer
    if map_abbr_to_team(normalize_abbr(name)) is not None:
        return None  # a team label ("4KANSAS"), not a scorer
    return number, name


def read_scorer_tokens(clip_path: Any, ocr: Any, sample_fps: float = SAMPLE_FPS) -> List[Dict[str, Any]]:
    """Per-frame scorer-graphic detections across the clip (BGR frames)."""
    dets: List[Dict[str, Any]] = []
    for t, frame in video.sample_frames(clip_path, sample_fps):
        band = frame[int(frame.shape[0] * BAND_TOP_FRAC) :, :]
        up = cv2.resize(band, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
        for _box, text, conf in ocr(up)[0] or []:
            if float(conf) < MIN_READ_CONF:
                continue
            parsed = parse_scorer_token(text)
            if parsed is not None:
                number, name = parsed
                dets.append({"t": round(float(t), 3), "number": number, "name": name, "conf": float(conf)})
    return dets


def aggregate_features(dets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse persistent per-frame detections into scorer "features".

    Detections of the same number within ``MERGE_GAP_SEC`` are one feature; a
    feature is kept only if seen in >= ``MIN_FRAMES`` frames (a stable graphic,
    not a one-frame OCR fluke). Each feature carries its time span and the modal
    OCR'd name.
    """
    by_num: Dict[str, List[Dict[str, Any]]] = {}
    for d in sorted(dets, key=lambda d: d["t"]):
        by_num.setdefault(d["number"], []).append(d)

    features: List[Dict[str, Any]] = []
    for number, group in by_num.items():
        run: List[Dict[str, Any]] = []

        def _flush(run: List[Dict[str, Any]]) -> None:
            if len(run) < MIN_FRAMES:
                return
            names = [d["name"] for d in run]
            features.append(
                {
                    "number": number,
                    "name": max(set(names), key=names.count),
                    "t_start": run[0]["t"],
                    "t_end": run[-1]["t"],
                    "n_frames": len(run),
                    "confidence": round(float(np.mean([d["conf"] for d in run])), 3),
                }
            )

        for d in group:
            if run and d["t"] - run[-1]["t"] > MERGE_GAP_SEC:
                _flush(run)
                run = []
            run.append(d)
        _flush(run)

    features.sort(key=lambda f: f["t_start"])
    return features


def run_stage(ctx: Any) -> None:  # ctx: libs.basketball.stages.StageContext
    """``scorer`` stage: OCR the scorer lower-third; emit {number, name, span}."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return
    base_fps = float(ctx.settings.base_fps)
    sample_fps = min(SAMPLE_FPS, base_fps) if base_fps > 0 else SAMPLE_FPS

    from rapidocr_onnxruntime import RapidOCR  # lazy: heavy import, stage-only

    ocr = RapidOCR()
    dets = read_scorer_tokens(ctx.clip_path, ocr, sample_fps)
    features = aggregate_features(dets)
    logger.info(
        "scorer: %d graphic(s) for clip %s: %s",
        len(features),
        ctx.clip_id,
        [(f["number"], f["name"]) for f in features],
    )
    ctx.cache.write_json(
        ctx.stage,
        {"clip_id": ctx.clip_id, "sample_fps": sample_fps, "n_detections": len(dets), "features": features},
    )
