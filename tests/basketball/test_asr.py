"""Unit tests for commentary cue extraction (libs/basketball/asr.py).

The Whisper transcription itself is not unit-tested (heavy optional dep); the
pure cue-extraction logic is.
"""

import pytest

from libs.basketball import asr


@pytest.mark.unit
class TestExtractCues:
    @staticmethod
    def _seg(t, text):
        return {"t_start": t, "t_end": t + 2.0, "text": text}

    def test_three_and_make(self):
        kinds = {c["kind"] for c in asr.extract_cues([self._seg(5.0, "Perry, for three! And it's good.")])}
        assert "three" in kinds and "make" in kinds

    def test_no_good_is_miss_not_make(self):
        kinds = {c["kind"] for c in asr.extract_cues([self._seg(5.0, "and it's no good, off the rim")])}
        assert "miss" in kinds and "make" not in kinds

    def test_make_cue(self):
        assert any(c["kind"] == "make" for c in asr.extract_cues([self._seg(5.0, "Kaluma buries it")]))

    def test_free_throw_cue(self):
        assert any(
            c["kind"] == "free_throw" for c in asr.extract_cues([self._seg(5.0, "steps to the free throw line")])
        )

    def test_no_cue_in_chatter(self):
        assert asr.extract_cues([self._seg(5.0, "he had a great season last year")]) == []

    def test_cue_carries_timestamp(self):
        cues = asr.extract_cues([self._seg(12.5, "no good")])
        assert cues and cues[0]["t"] == 12.5
