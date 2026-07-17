"""Shared camera-cut detection — HSV-histogram total-variation distance.

Consolidates the identical detectors that previously lived in shots.py and
teams.py (both were marked TODO(consolidate)). One canonical whole-frame
histogram + metric, two entry points:

* ``detect_cuts(clip, fps, threshold)`` — standalone pass over a clip
  (used by the shots stage).
* ``CutTracker`` — incremental per-frame use inside an existing decode loop
  (used by the teams stage, which also resets its ByteTrack tracker at each
  cut).

Metric: each sampled frame is downscaled to 96x54 and reduced to a
normalized 8x4x4 HSV histogram; the total-variation distance (in [0, 1])
between consecutive frames' histograms above the threshold marks a cut. The
cut timestamp is the midpoint between the two frames spanning the jump.

Both ``shots_cut_threshold`` and ``teams_cut_threshold`` (default 0.5) feed
this same detector — they stay separate settings so the stages can be tuned
independently.
"""

from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np

# Downscale target + histogram bins for the whole-frame signature.
_ANALYSIS_SIZE = (96, 54)  # (width, height)
_HSV_BINS = [8, 4, 4]
_HSV_RANGES = [0, 180, 0, 256, 0, 256]


def frame_histogram(frame_bgr: np.ndarray) -> np.ndarray:
    """Coarse whole-frame HSV histogram (normalized), for cut detection."""
    small = cv2.resize(frame_bgr, _ANALYSIS_SIZE, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, _HSV_BINS, _HSV_RANGES).ravel()
    total = float(hist.sum())
    return hist / total if total > 0 else hist


def histogram_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Total-variation distance between two normalized histograms, in [0, 1]."""
    return float(0.5 * np.abs(a - b).sum())


class CutTracker:
    """Incremental cut detector: feed frames in decode order via ``update``.

    ``update`` returns True when a cut lands between the previous frame and
    this one; the cut timestamp (midpoint of the two frames' PTS times) is
    appended to ``cuts``.
    """

    def __init__(self, threshold: float) -> None:
        self.threshold = float(threshold)
        self.cuts: List[float] = []
        self._prev_hist: Optional[np.ndarray] = None
        self._prev_t = 0.0

    def update(self, t: float, frame_bgr: np.ndarray) -> bool:
        hist = frame_histogram(frame_bgr)
        is_cut = False
        if self._prev_hist is not None and histogram_distance(self._prev_hist, hist) > self.threshold:
            self.cuts.append(round((self._prev_t + t) / 2.0, 6))
            is_cut = True
        self._prev_hist, self._prev_t = hist, t
        return is_cut


def detect_cuts(clip_path: Union[str, Path], fps: float, threshold: float) -> List[float]:
    """Camera-cut timestamps for a whole clip, sampled at ``fps``."""
    from libs.basketball.video import sample_frames

    tracker = CutTracker(threshold)
    for t, frame in sample_frames(clip_path, fps):
        tracker.update(t, frame)
    return tracker.cuts
