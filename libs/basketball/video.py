"""PyAV-based decoding with frame-exact PTS timestamps.

Every timestamp in the pipeline originates here, from PTS — never from
frame-index x fps assumptions (OpenCV seeking is unreliable; VFR clips have
PTS gaps). Two-tier sampling: ``sample_frames`` for the cheap base pass,
``decode_window`` for native-fps re-decode around events.

Also implements the ``decode`` pipeline stage (see libs/basketball/stages.py):
it probes the clip and records the base-pass sampling timestamps. Frames
themselves are never cached — later stages re-decode on demand.
"""

from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple, Union

import av
import numpy as np

FrameTuple = Tuple[float, np.ndarray]  # (t_sec from PTS, BGR HxWx3 uint8)


def _open_video(path: Union[str, Path]) -> Tuple[av.container.InputContainer, Any]:
    """Open a clip and return (container, video stream) or raise ValueError."""
    container = av.open(str(path))
    if not container.streams.video:
        container.close()
        raise ValueError(f"No video stream in {path}")
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"
    return container, stream


def _frame_time(frame: av.VideoFrame, stream: Any) -> Optional[float]:
    """Frame timestamp in seconds, strictly from PTS (fallback: DTS)."""
    ts = frame.pts if frame.pts is not None else frame.dts
    if ts is None:
        return None
    time_base = frame.time_base or stream.time_base
    if time_base is None:
        return None
    return float(ts * time_base)


def probe(path: Union[str, Path]) -> Dict[str, Any]:
    """Container/stream metadata: duration (sec), fps, resolution."""
    container, stream = _open_video(path)
    try:
        duration = None
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        elif container.duration is not None:
            duration = container.duration / av.time_base
        fps = float(stream.average_rate) if stream.average_rate else None
        return {
            "duration_sec": duration,
            "fps": fps,
            "width": stream.codec_context.width,
            "height": stream.codec_context.height,
            "num_frames": stream.frames or None,
            "codec": stream.codec_context.name,
        }
    finally:
        container.close()


def sample_frames(path: Union[str, Path], fps: float) -> Iterator[FrameTuple]:
    """Base decode pass: yield (t_sec, BGR frame) at roughly ``fps``.

    Decodes every frame (no seeking) and emits the first frame at/after each
    sampling target; the next target is ``yielded_t + 1/fps``, so spacing is
    correct even across VFR PTS gaps. Timestamps come from PTS.
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    interval = 1.0 / fps
    container, stream = _open_video(path)
    try:
        next_target: Optional[float] = None
        for frame in container.decode(stream):
            t = _frame_time(frame, stream)
            if t is None:
                continue
            if next_target is None or t >= next_target:
                yield t, frame.to_ndarray(format="bgr24")
                next_target = t + interval
    finally:
        container.close()


def decode_window(path: Union[str, Path], t0: float, t1: float) -> Iterator[FrameTuple]:
    """Native-fps re-decode of the window [t0, t1] (seconds, inclusive).

    Seeks to the nearest keyframe before t0, then yields every frame whose
    PTS falls inside the window.
    """
    if t1 < t0:
        raise ValueError(f"decode_window: t1 ({t1}) < t0 ({t0})")
    container, stream = _open_video(path)
    try:
        seek_to = max(t0, 0.0)
        time_base = stream.time_base or Fraction(1, av.time_base)
        container.seek(int(seek_to / time_base), stream=stream, backward=True)
        for frame in container.decode(stream):
            t = _frame_time(frame, stream)
            if t is None:
                continue
            if t < t0:
                continue
            if t > t1:
                break
            yield t, frame.to_ndarray(format="bgr24")
    finally:
        container.close()


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``decode`` stage: probe the clip + record base-pass PTS timestamps.

    output.json: {clip_id, probe{duration_sec,fps,width,height,...},
    base_fps, num_sampled_frames, frame_timestamps[]}. Frames are not
    cached — downstream stages re-decode via sample_frames/decode_window.
    """
    info = probe(ctx.clip_path)
    base_fps = ctx.settings.base_fps
    timestamps = [round(t, 6) for t, _frame in sample_frames(ctx.clip_path, base_fps)]
    ctx.cache.write_json(
        ctx.stage,
        {
            "clip_id": ctx.clip_id,
            "probe": info,
            "base_fps": base_fps,
            "num_sampled_frames": len(timestamps),
            "frame_timestamps": timestamps,
        },
    )
