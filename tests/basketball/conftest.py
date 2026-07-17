"""Fixtures for basketball tests: synthetic PyAV-generated clips.

These tests run in the standalone basketball venv (.venv-basketball/) with:

    .venv-basketball/bin/python -m pytest tests/basketball -m unit
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

WIDTH, HEIGHT = 320, 240
RATE = 30


def write_synthetic_clip(path: Path, pts_list, rate: int = RATE) -> Path:
    """Encode one frame per PTS value (units of 1/rate sec) into an MP4."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=rate)
    stream.width, stream.height = WIDTH, HEIGHT
    stream.pix_fmt = "yuv420p"
    for i, pts in enumerate(pts_list):
        img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        img[:, :, 0] = (i * 7) % 256  # varying content so encoding isn't degenerate
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        frame.pts = pts
        frame.time_base = Fraction(1, rate)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return path


@pytest.fixture(scope="session")
def cfr_clip(tmp_path_factory) -> Path:
    """3 s constant-frame-rate clip: 90 frames @ 30 fps."""
    path = tmp_path_factory.mktemp("clips") / "synthetic_cfr.mp4"
    return write_synthetic_clip(path, list(range(90)))


@pytest.fixture(scope="session")
def vfr_clip(tmp_path_factory) -> Path:
    """Variable-frame-rate clip: 1 s of frames, a 1 s PTS gap, 1 s of frames."""
    path = tmp_path_factory.mktemp("clips") / "synthetic_vfr.mp4"
    return write_synthetic_clip(path, list(range(30)) + list(range(60, 90)))


@pytest.fixture
def corrupt_clip(tmp_path) -> Path:
    path = tmp_path / "corrupt.mp4"
    path.write_bytes(b"this is definitely not an mp4 file" * 64)
    return path
