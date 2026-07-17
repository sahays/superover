"""Synthetic broadcast fixtures for score-bug OCR tests.

Renders 640x360 clips with moving "game" content and a static bottom score
bar (team abbreviations, scores, ticking clock via cv2.putText), encoded with
PyAV like tests/basketball/conftest.py. The score sequence, hidden-bug
intervals, and single-read OCR-hostile flickers are scripted.
"""

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Dict, List, Tuple

import av
import cv2
import numpy as np

WIDTH, HEIGHT = 640, 360
RATE = 30

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_WHITE = (240, 240, 240)
_BAR_BG = (24, 24, 30)

# Bar geometry (render-side only — the stage must derive its own ROIs).
_BAR_Y0, _BAR_Y1 = 306, 354
_BAR_X0, _BAR_X1 = 8, 632
_TEXT_Y = 340
_X_ABBR_L, _X_SCORE_L, _X_CLOCK, _X_SCORE_R, _X_ABBR_R = 24, 130, 272, 430, 500


@dataclass
class ScoreScript:
    """Scripted scoreboard behavior for one synthetic clip."""

    duration: float = 24.0
    start_scores: Dict[str, int] = field(default_factory=lambda: {"left": 35, "right": 51})
    abbrs: Dict[str, str] = field(default_factory=lambda: {"left": "KU", "right": "KSU"})
    changes: List[Tuple[float, str, int]] = field(default_factory=list)  # (t, side, delta)
    hidden: List[Tuple[float, float]] = field(default_factory=list)  # [t0, t1) bug hidden
    flickers: List[Tuple[float, float, str, int]] = field(default_factory=list)  # (t0, t1, side, wrong)
    clock_start: float = 754.0  # 12:34
    show_bar: bool = True

    def scores_at(self, t: float) -> Dict[str, int]:
        scores = dict(self.start_scores)
        for change_t, side, delta in sorted(self.changes):
            if t >= change_t:
                scores[side] += delta
        return scores

    def bar_hidden_at(self, t: float) -> bool:
        return any(t0 <= t < t1 for t0, t1 in self.hidden)

    def displayed_at(self, t: float) -> Dict[str, int]:
        scores = self.scores_at(t)
        for t0, t1, side, wrong in self.flickers:
            if t0 <= t < t1:
                scores[side] = wrong
        return scores


def default_script() -> ScoreScript:
    """The scenario the integration tests assert against.

    KU 35->37 at t=8, KSU 51->54 at t=15, a single-read OCR-hostile flicker
    (35 shown as 85) around t=5, the bug hidden 17.5-20.5 s, and KSU 54->56
    at t=19 while hidden (must surface as one resync window event).
    """
    return ScoreScript(
        duration=24.0,
        changes=[(8.0, "left", 2), (15.0, "right", 3), (19.0, "right", 2)],
        hidden=[(17.5, 20.5)],
        flickers=[(5.0, 5.45, "left", 85)],
    )


def _background(t: float, rng: np.random.Generator) -> np.ndarray:
    """Moving-noise 'game' content: scrolling gradient + per-frame noise."""
    xx, yy = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    phase = int(t * 173)
    base = ((xx * 3 + yy * 2 + phase) % 256).astype(np.uint8)
    frame = np.stack([base, np.roll(base, 37, axis=1), np.roll(base, 91, axis=0)], axis=-1)
    noise = rng.integers(0, 60, size=(HEIGHT, WIDTH, 3), dtype=np.uint8)
    return cv2.add(frame, noise)


def _draw_bar(frame: np.ndarray, script: ScoreScript, t: float) -> None:
    scores = script.displayed_at(t)
    clock = max(0.0, script.clock_start - t)
    clock_text = f"{int(clock) // 60}:{int(clock) % 60:02d}"
    cv2.rectangle(frame, (_BAR_X0, _BAR_Y0), (_BAR_X1, _BAR_Y1), _BAR_BG, -1)
    cv2.line(frame, (_BAR_X0, _BAR_Y0 + 1), (_BAR_X1, _BAR_Y0 + 1), (200, 200, 200), 1)
    for text, x in (
        (script.abbrs["left"], _X_ABBR_L),
        (str(scores["left"]), _X_SCORE_L),
        (clock_text, _X_CLOCK),
        (str(scores["right"]), _X_SCORE_R),
        (script.abbrs["right"], _X_ABBR_R),
    ):
        cv2.putText(frame, text, (x, _TEXT_Y), _FONT, 0.9, _WHITE, 2, cv2.LINE_AA)


def render_frame(script: ScoreScript, t: float, rng: np.random.Generator) -> np.ndarray:
    frame = _background(t, rng)
    if script.show_bar and not script.bar_hidden_at(t):
        _draw_bar(frame, script, t)
    return frame


def write_scorebug_clip(path: Path, script: ScoreScript, rate: int = RATE) -> Path:
    """Encode the scripted scenario into an MP4 (mpeg4, high bitrate)."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=rate)
    stream.width, stream.height = WIDTH, HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 8_000_000
    rng = np.random.default_rng(20260717)
    num_frames = int(round(script.duration * rate))
    for i in range(num_frames):
        t = i / rate
        img = render_frame(script, t, rng)
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        frame.pts = i
        frame.time_base = Fraction(1, rate)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return path
