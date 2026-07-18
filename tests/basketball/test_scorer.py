"""Unit tests for the scorer lower-third graphic reader (libs/basketball/scorer.py)."""

import pytest

from libs.basketball import scorer


@pytest.mark.unit
class TestParseScorerToken:
    def test_number_and_name(self):
        assert scorer.parse_scorer_token("24ARTHURKALUMA") == ("24", "ARTHURKALUMA")

    def test_interior_spaces_stripped(self):
        assert scorer.parse_scorer_token("2 TYLOR PERRY") == ("2", "TYLORPERRY")

    def test_team_label_rejected(self):
        # The score bug's ranked-team label "(4) KANSAS" OCRs as "4KANSAS".
        assert scorer.parse_scorer_token("4KANSAS") is None
        assert scorer.parse_scorer_token("4KANSASST") is None

    def test_long_caption_rejected(self):
        assert scorer.parse_scorer_token("21STSEASONASKANSASHEADCOACH") is None

    def test_non_scorer_tokens_rejected(self):
        assert scorer.parse_scorer_token("16:53") is None  # clock
        assert scorer.parse_scorer_token("41") is None  # bare score
        assert scorer.parse_scorer_token("5PTS") is None  # stat token, name too short


@pytest.mark.unit
class TestAggregateFeatures:
    @staticmethod
    def _d(t, number="24", name="KALUMA", conf=0.99):
        return {"t": t, "number": number, "name": name, "conf": conf}

    def test_persistent_graphic_becomes_feature(self):
        feats = scorer.aggregate_features([self._d(t) for t in (25.0, 25.5, 26.0, 26.5)])
        assert len(feats) == 1
        assert feats[0]["number"] == "24" and feats[0]["n_frames"] == 4
        assert (feats[0]["t_start"], feats[0]["t_end"]) == (25.0, 26.5)

    def test_flicker_below_min_frames_dropped(self):
        assert scorer.aggregate_features([self._d(25.0), self._d(25.5)]) == []

    def test_gap_splits_into_two_features(self):
        dets = [self._d(t) for t in (2.0, 2.5, 3.0)] + [self._d(t) for t in (25.0, 25.5, 26.0)]
        feats = scorer.aggregate_features(dets)
        assert len(feats) == 2
        assert [f["t_start"] for f in feats] == [2.0, 25.0]
