"""Annotated debug-video rendering — the CLI's ``--debug-video`` QA tool.

Re-decodes the clip at the base sampling fps and overlays every cached
signal onto the frames:

* detection boxes colored by class (when the detect stage ran),
* player track IDs + team-cluster colors (teams stage),
* the scorebug ROI + the current smoothed score reads (scorebug stage),
* an event banner around each fused event's timestamp (fuse stage).

Everything is read from the per-clip stage cache; a missing or skipped
stage simply drops its overlay — the tool must render something useful on
any partially-run clip and never fail the run over a bad overlay. Output is
an mpeg4 MP4 written with PyAV, one output frame per sampled frame.
"""

import logging
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import av
import cv2
import numpy as np

from libs.basketball.cache import ClipCache
from libs.basketball.video import sample_frames

logger = logging.getLogger(__name__)

# BGR colors per canonical detection class (libs/basketball/detect.py ids 0-5).
CLASS_COLORS: Dict[str, Tuple[int, int, int]] = {
    "ball": (0, 165, 255),  # orange
    "rim": (0, 255, 255),  # yellow
    "ball_in_basket": (0, 0, 255),  # red
    "player": (0, 200, 0),  # green
    "number": (255, 0, 255),  # magenta
    "referee": (160, 160, 160),  # gray
}
DEFAULT_CLASS_COLOR = (255, 255, 0)  # cyan-ish for pass-through classes
CLUSTER_COLORS = {0: (255, 128, 0), 1: (0, 64, 255)}  # cluster 0 blue-ish, 1 red-ish
SCOREBUG_COLOR = (255, 255, 255)
BANNER_COLOR = (40, 40, 40)
BANNER_TEXT_COLOR = (255, 255, 255)
_FONT = cv2.FONT_HERSHEY_SIMPLEX

# A fused event's banner shows from slightly before t to after t (or t_end).
BANNER_LEAD_SEC = 0.5
BANNER_TAIL_SEC = 1.5

# Detection overlay tolerance: sampled PTS must match detect's frame_t.
_PTS_MATCH_TOL = 1e-3


def _read_optional(cache: ClipCache, stage: str, filename: str = "output.json") -> Optional[Dict[str, Any]]:
    """Stage output, or None when absent/skipped/unreadable (QA tool: never raise)."""
    try:
        data = cache.read_json(stage, filename)
    except (FileNotFoundError, ValueError):
        return None
    if isinstance(data, dict) and data.get("skipped"):
        return None
    return data if isinstance(data, dict) else None


def _read_optional_arrays(cache: ClipCache, stage: str) -> Optional[Dict[str, np.ndarray]]:
    try:
        return cache.read_arrays(stage)
    except FileNotFoundError:
        return None


def _row_maps(teams_out: Optional[Dict[str, Any]]) -> Dict[int, Tuple[int, Optional[int]]]:
    """detect npz row -> (track_id, cluster) from the teams output."""
    out: Dict[int, Tuple[int, Optional[int]]] = {}
    for track in (teams_out or {}).get("tracks", []):
        for row in track.get("det_rows", []):
            out[int(row)] = (int(track["track_id"]), track.get("cluster"))
    return out


def _event_label(event: Dict[str, Any]) -> str:
    parts = [f"{event.get('t', 0.0):.1f}s", str(event.get("type", "?"))]
    if event.get("outcome"):
        parts.append(str(event["outcome"]))
    if event.get("points") is not None:
        parts.append(f"+{event['points']}")
    if event.get("team"):
        parts.append(str(event["team"]))
    if event.get("jersey"):
        parts.append(f"#{event['jersey']}")
    return " ".join(parts)


def _draw_detections(
    frame: np.ndarray,
    k: int,
    t: float,
    detect_arrays: Dict[str, np.ndarray],
    class_names: List[str],
    row_to_track: Dict[int, Tuple[int, Optional[int]]],
) -> None:
    frame_t = detect_arrays["frame_t"]
    if k >= frame_t.shape[0] or abs(t - float(frame_t[k])) > _PTS_MATCH_TOL:
        return  # sampling drifted from the detect cache — skip the overlay
    rows = np.where(detect_arrays["frame_idx"] == k)[0]
    for row in rows:
        class_id = int(detect_arrays["class_ids"][row])
        name = class_names[class_id] if class_id < len(class_names) else f"class_{class_id}"
        color = CLASS_COLORS.get(name, DEFAULT_CLASS_COLOR)
        label = name
        tracked = row_to_track.get(int(row))
        if tracked is not None:
            track_id, cluster = tracked
            label = f"T{track_id} {name}"
            if cluster is not None:
                color = CLUSTER_COLORS.get(int(cluster), color)
                label = f"T{track_id} c{cluster}"
        x1, y1, x2, y2 = (int(round(float(v))) for v in detect_arrays["boxes"][row])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(12, y1 - 4)), _FONT, 0.4, color, 1, cv2.LINE_AA)


def _draw_scorebug(frame: np.ndarray, t: float, scorebug_out: Dict[str, Any]) -> None:
    roi = scorebug_out.get("roi")
    if not roi:
        return
    x, y, w, h = (int(round(float(v))) for v in roi)
    cv2.rectangle(frame, (x, y), (x + w, y + h), SCOREBUG_COLOR, 1)
    current = None
    for read in scorebug_out.get("reads", []):
        if float(read.get("raw_t", 0.0)) <= t:
            current = read
        else:
            break
    if current is None:
        return
    smoothed = current.get("smoothed") or {}
    left, right = smoothed.get("left"), smoothed.get("right")
    text = f"bug {left if left is not None else '?'}-{right if right is not None else '?'}"
    if not current.get("visible", True):
        text += " (hidden)"
    cv2.putText(frame, text, (x, max(12, y - 6)), _FONT, 0.5, SCOREBUG_COLOR, 1, cv2.LINE_AA)


def _draw_banner(frame: np.ndarray, t: float, events: List[Dict[str, Any]]) -> None:
    active = [
        e
        for e in events
        if float(e.get("t", 0.0)) - BANNER_LEAD_SEC
        <= t
        <= float(e.get("t_end") if e.get("t_end") is not None else e.get("t", 0.0)) + BANNER_TAIL_SEC
    ]
    if not active:
        return
    text = " | ".join(_event_label(e) for e in active[:2])
    height = 24
    overlay = frame[:height, :].copy()
    frame[:height, :] = BANNER_COLOR
    cv2.addWeighted(frame[:height, :], 0.8, overlay, 0.2, 0, dst=frame[:height, :])
    cv2.putText(frame, text, (6, 17), _FONT, 0.5, BANNER_TEXT_COLOR, 1, cv2.LINE_AA)


def render_debug_video(clip_path: Path, cache: ClipCache, settings: Any, out_path: Path) -> int:
    """Render the annotated MP4 to ``out_path``; returns the frame count."""
    detect_out = _read_optional(cache, "detect")
    detect_arrays = _read_optional_arrays(cache, "detect") if detect_out else None
    class_names: List[str] = list(((detect_out or {}).get("model") or {}).get("classes") or [])
    teams_out = _read_optional(cache, "teams")
    scorebug_out = _read_optional(cache, "scorebug")
    fuse_out = _read_optional(cache, "fuse")
    events = list((fuse_out or {}).get("events", []))
    row_to_track = _row_maps(teams_out)

    fps = Fraction(settings.base_fps).limit_denominator(1000)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    container = av.open(str(out_path), mode="w")
    stream = None
    n_frames = 0
    try:
        for k, (t, frame) in enumerate(sample_frames(clip_path, settings.base_fps)):
            frame = np.ascontiguousarray(frame[: frame.shape[0] // 2 * 2, : frame.shape[1] // 2 * 2])
            if detect_arrays is not None:
                _draw_detections(frame, k, t, detect_arrays, class_names, row_to_track)
            if scorebug_out is not None:
                _draw_scorebug(frame, t, scorebug_out)
            _draw_banner(frame, t, events)
            cv2.putText(frame, f"t={t:6.2f}s", (6, frame.shape[0] - 8), _FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            if stream is None:
                stream = container.add_stream("mpeg4", rate=fps)
                stream.width, stream.height = frame.shape[1], frame.shape[0]
                stream.pix_fmt = "yuv420p"
                stream.bit_rate = 4_000_000
            video_frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(frame[:, :, ::-1]), format="rgb24")
            video_frame.pts = n_frames
            video_frame.time_base = 1 / fps
            for packet in stream.encode(video_frame):
                container.mux(packet)
            n_frames += 1
        if stream is not None:
            for packet in stream.encode():
                container.mux(packet)
    finally:
        container.close()
    if n_frames == 0:
        raise ValueError(f"debug video: no frames decoded from {clip_path}")
    logger.info("debug video: %d frame(s) -> %s", n_frames, out_path)
    return n_frames
