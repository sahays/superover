"""Unit tests for libs/basketball/video.py (PyAV decode, PTS timestamps)."""

import av
import numpy as np
import pytest

from libs.basketball import video

pytestmark = pytest.mark.unit


class TestProbe:
    def test_probe_cfr(self, cfr_clip):
        info = video.probe(cfr_clip)
        assert info["duration_sec"] == pytest.approx(3.0, abs=0.1)
        assert info["fps"] == pytest.approx(30.0, abs=0.5)
        assert info["width"] == 320
        assert info["height"] == 240
        assert info["num_frames"] == 90

    def test_probe_corrupt_raises(self, corrupt_clip):
        with pytest.raises(av.error.FFmpegError):
            video.probe(corrupt_clip)


class TestSampleFrames:
    def test_pts_monotonic(self, cfr_clip):
        timestamps = [t for t, _frame in video.sample_frames(cfr_clip, 8.0)]
        assert len(timestamps) > 0
        assert all(b > a for a, b in zip(timestamps, timestamps[1:])), "PTS must be strictly increasing"
        assert timestamps[0] == pytest.approx(0.0)
        assert timestamps[-1] <= 3.0

    def test_sampling_rate_roughly_respected(self, cfr_clip):
        timestamps = [t for t, _frame in video.sample_frames(cfr_clip, 8.0)]
        # ~8 fps over 3 s => ~24 frames; spacing never below 1/8 s
        assert 18 <= len(timestamps) <= 26
        gaps = [b - a for a, b in zip(timestamps, timestamps[1:])]
        assert min(gaps) >= 1.0 / 8.0 - 1e-6

    def test_vfr_gap_timestamps_from_pts(self, vfr_clip):
        """PTS gaps (VFR) must show up in timestamps, not be papered over."""
        timestamps = [t for t, _frame in video.sample_frames(vfr_clip, 8.0)]
        assert all(b > a for a, b in zip(timestamps, timestamps[1:]))
        # Frames exist for [0, 1) and [2, 3); nothing may be reported inside the gap.
        assert not [t for t in timestamps if 1.0 < t < 2.0 - 1e-6]
        assert any(t >= 2.0 - 1e-6 for t in timestamps), "frames after the PTS gap must be sampled"

    def test_frames_are_bgr_ndarrays(self, cfr_clip):
        _t, frame = next(iter(video.sample_frames(cfr_clip, 8.0)))
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8

    def test_bad_fps_rejected(self, cfr_clip):
        with pytest.raises(ValueError):
            list(video.sample_frames(cfr_clip, 0.0))

    def test_corrupt_clip_raises(self, corrupt_clip):
        with pytest.raises(av.error.FFmpegError):
            list(video.sample_frames(corrupt_clip, 8.0))


class TestDecodeWindow:
    def test_window_native_fps(self, cfr_clip):
        frames = list(video.decode_window(cfr_clip, 1.0, 2.0))
        timestamps = [t for t, _f in frames]
        assert all(1.0 <= t <= 2.0 for t in timestamps)
        assert all(b > a for a, b in zip(timestamps, timestamps[1:]))
        # native 30 fps over a 1 s inclusive window => ~31 frames
        assert 28 <= len(frames) <= 32

    def test_window_clamps_negative_start(self, cfr_clip):
        timestamps = [t for t, _f in video.decode_window(cfr_clip, -1.0, 0.5)]
        assert timestamps and timestamps[0] == pytest.approx(0.0)

    def test_inverted_window_rejected(self, cfr_clip):
        with pytest.raises(ValueError):
            list(video.decode_window(cfr_clip, 2.0, 1.0))
