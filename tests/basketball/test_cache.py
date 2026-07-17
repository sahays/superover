"""Unit tests for the per-clip stage cache (libs/basketball/cache.py)."""

import re

import numpy as np
import pytest

from libs.basketball.cache import ClipCache, compute_clip_id

pytestmark = pytest.mark.unit


class TestClipId:
    def test_format(self, tmp_path):
        clip = tmp_path / "shot_0013.mp4"
        clip.write_bytes(b"fake video bytes")
        clip_id = compute_clip_id(clip)
        assert re.fullmatch(r"shot_0013-[0-9a-f]{8}", clip_id)

    def test_content_addressed(self, tmp_path):
        a = tmp_path / "clip.mp4"
        b = tmp_path / "sub" / "clip.mp4"
        b.parent.mkdir()
        a.write_bytes(b"same content")
        b.write_bytes(b"same content")
        assert compute_clip_id(a) == compute_clip_id(b)
        b.write_bytes(b"different content")
        assert compute_clip_id(a) != compute_clip_id(b)


class TestClipCache:
    def test_json_round_trip(self, tmp_path):
        cache = ClipCache(tmp_path, "clip-deadbeef")
        payload = {"events": [{"t": 1.5, "type": "shot"}], "nested": {"a": [1, 2, 3]}, "text": "ok"}
        assert not cache.is_warm("scorebug")
        cache.write_json("scorebug", payload)
        assert cache.is_warm("scorebug")
        assert cache.read_json("scorebug") == payload

    def test_json_byte_identical_reload(self, tmp_path):
        cache = ClipCache(tmp_path, "clip-deadbeef")
        path = cache.write_json("decode", {"timestamps": [0.0, 0.125, 0.25]})
        first = path.read_bytes()
        cache.write_json("decode", {"timestamps": [0.0, 0.125, 0.25]})
        assert path.read_bytes() == first

    def test_arrays_round_trip(self, tmp_path):
        cache = ClipCache(tmp_path, "clip-deadbeef")
        arrays = {
            "timestamps": np.linspace(0, 30, 240),
            "boxes": np.arange(24, dtype=np.float32).reshape(6, 4),
        }
        cache.write_arrays("detect", arrays)
        loaded = cache.read_arrays("detect")
        assert set(loaded) == set(arrays)
        for key in arrays:
            np.testing.assert_array_equal(loaded[key], arrays[key])

    def test_arrays_do_not_mark_warm(self, tmp_path):
        cache = ClipCache(tmp_path, "clip-deadbeef")
        cache.write_arrays("detect", {"x": np.zeros(3)})
        assert not cache.is_warm("detect"), "only output.json marks a stage warm"

    def test_missing_reads_raise(self, tmp_path):
        cache = ClipCache(tmp_path, "clip-deadbeef")
        with pytest.raises(FileNotFoundError):
            cache.read_json("nope")
        with pytest.raises(FileNotFoundError):
            cache.read_arrays("nope")

    def test_layout(self, tmp_path):
        cache = ClipCache(tmp_path, "shot_0013-1a2b3c4d")
        cache.write_json("decode", {"ok": True})
        assert (tmp_path / "shot_0013-1a2b3c4d" / "decode" / "output.json").is_file()
        artifact = cache.path("decode", "frames.npz")
        assert artifact.parent == tmp_path / "shot_0013-1a2b3c4d" / "decode"
