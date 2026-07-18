"""Unit tests for the play-by-play join (libs/basketball/pbp.py)."""

import json

import pytest

from libs.basketball import pbp
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import make_context
from tests.basketball import pbp_fixtures

GAME = pbp_fixtures.normalized_game()
PLAYS = GAME["plays"]
INDEX = pbp.build_score_index(PLAYS)
AWAY, HOME = "kansas", "kansas-state"


def _match(score_after, left="kansas", right="kansas-state", clock=None, tol=40.0):
    return pbp.match_score_after(score_after, left, right, clock, AWAY, HOME, INDEX, PLAYS, tol)


@pytest.mark.unit
class TestNormalizeShotType:
    def test_points_decide_ft_and_3pt(self):
        assert pbp.normalize_shot_type("JumpShot", "made Three Point Jumper", 3) == "3pt"
        assert pbp.normalize_shot_type("FreeThrow", "made Free Throw", 1) == "ft"

    def test_two_point_flavors_from_text(self):
        assert pbp.normalize_shot_type("LayUpShot", "made Layup", 2) == "layup"
        assert pbp.normalize_shot_type("DunkShot", "made Dunk", 2) == "dunk"
        assert pbp.normalize_shot_type("JumpShot", "made Jumper", 2) == "jumper"
        assert pbp.normalize_shot_type("", "put it in", 2) == "other"


@pytest.mark.unit
class TestScoreIndex:
    def test_unique_and_ignores_misses(self):
        # The missed dunk (made=False, 9-8) is never indexed.
        assert (9, 8) not in INDEX
        assert INDEX[(41, 32)]["scorer_name"] == "Arthur Kaluma"
        assert len([p for p in PLAYS if p["made"]]) == len(INDEX)


@pytest.mark.unit
class TestMatchScoreAfter:
    def test_exact_known_orientation(self):
        r = _match([41, 32])
        assert r and r.play["scorer_name"] == "Arthur Kaluma" and r.play["scorer_jersey"] == "24"
        assert r.method == "score_exact" and r.orientation_known and r.confidence == 0.98

    def test_reversed_scorebug_orientation(self):
        # scorebug left=kansas-state, right=kansas -> values [32, 41], resolved by team keys.
        r = _match([32, 41], left="kansas-state", right="kansas")
        assert r and r.play["scorer_name"] == "Arthur Kaluma"

    def test_unknown_orientation_single_ordering(self):
        r = _match([41, 32], left=None, right=None)
        assert r and r.play["scorer_name"] == "Arthur Kaluma"
        assert not r.orientation_known and r.confidence == 0.9

    def test_and_one_fg_vs_ft_same_clock(self):
        # Both plays share clock 18:58 but are distinct score states -> score_after wins.
        assert _match([2, 3]).play["shot_type"] == "layup"
        assert _match([3, 3]).play["shot_type"] == "ft"

    def test_symmetric_tie_unknown_orientation(self):
        r = _match([41, 41], left=None, right=None)
        assert r and (r.play["away_score"], r.play["home_score"]) == (41, 41)

    def test_ocr_off_by_one_clock_fallback(self):
        r = _match([41, 31], clock=pbp_fixtures._clock_sec("17:00"))  # truth 41-32
        assert r and r.play["scorer_name"] == "Arthur Kaluma" and r.method == "clock_fallback"
        assert r.confidence == 0.7

    def test_ot_period_safety_in_fallback(self):
        # Truth 50-48 (2nd half, 5:00); OCR reads 50-47. OT has 70-68 at the same clock.
        r = _match([50, 47], clock=pbp_fixtures._clock_sec("5:00"))
        assert r and (r.play["away_score"], r.play["home_score"]) == (50, 48)  # not the OT 70-68

    def test_no_match_no_clock_returns_none(self):
        assert _match([99, 98]) is None
        assert _match([None, None]) is None

    def test_two_hit_ambiguous_disambiguated_by_clock(self):
        # Defensive branch: a synthetic index holding both orderings (impossible in a
        # real monotonic game) -> clock breaks the tie.
        p_a = pbp_fixtures.play(1, "10:00", 2, 10, 8, "away", "A", "1", "layup")
        p_b = pbp_fixtures.play(1, "5:00", 2, 8, 10, "home", "B", "2", "layup")
        idx2, plays2 = {(10, 8): p_a, (8, 10): p_b}, [p_a, p_b]
        r = pbp.match_score_after([10, 8], None, None, pbp_fixtures._clock_sec("5:00"), AWAY, HOME, idx2, plays2, 40.0)
        assert r and r.play["scorer_name"] == "B" and r.method == "score_exact_clock"


@pytest.mark.unit
class TestRecoverSilentMiss:
    # the fixture has one missed shot: Will McNair Jr. #13, 9-8, 14:00 (840 s), 1st half.
    def test_single_consistent_miss_recovered(self):
        r = pbp.recover_silent_miss(PLAYS, {(9, 8)}, (840.0, 840.0), 1, 4.0)
        assert r and r["scorer_name"] == "Will McNair Jr." and not r["made"]

    def test_ambiguous_window_declines(self):
        m1 = pbp_fixtures.play(1, "14:00", 2, 9, 8, "home", "A", "1", "layup", made=False)
        m2 = pbp_fixtures.play(1, "14:02", 2, 9, 8, "away", "B", "2", "3pt", made=False)
        assert pbp.recover_silent_miss([m1, m2], {(9, 8)}, (838.0, 842.0), 1, 4.0) is None

    def test_score_not_observed_declines(self):
        # the 9-8 miss is not consistent with an observed 3-6.
        assert pbp.recover_silent_miss(PLAYS, {(3, 6)}, (840.0, 840.0), 1, 4.0) is None

    def test_wrong_period_declines(self):
        assert pbp.recover_silent_miss(PLAYS, {(9, 8)}, (840.0, 840.0), 2, 4.0) is None

    def test_clock_out_of_window_declines(self):
        assert pbp.recover_silent_miss(PLAYS, {(9, 8)}, (900.0, 900.0), 1, 4.0) is None


@pytest.mark.unit
class TestRunStage:
    def _ctx(self, tmp_path, game_id="", cache_dir="", allow_fetch=False, force=True):
        settings = BasketballSettings(
            workdir=str(tmp_path / "work"),
            pbp_game_id=game_id,
            pbp_cache_dir=str(cache_dir),
            pbp_allow_fetch=allow_fetch,
        )
        return make_context("pbp", tmp_path / "clip.mp4", "clip-x", settings, tmp_path / "work", force=force)

    def test_no_game_id_skips(self, tmp_path):
        ctx = self._ctx(tmp_path)
        pbp.run_stage(ctx)
        out = ctx.cache.read_json("pbp")
        assert out.get("skipped") and "no game_id" in out["reason"]

    def test_loads_cached_file(self, tmp_path):
        cache = tmp_path / "pbp"
        cache.mkdir()
        (cache / "401603459.json").write_text(json.dumps(GAME))
        ctx = self._ctx(tmp_path, game_id="401603459", cache_dir=cache)
        pbp.run_stage(ctx)
        out = ctx.cache.read_json("pbp")
        assert not out.get("skipped")
        assert out["plays"][5]["scorer_name"] == "Arthur Kaluma"

    def test_missing_cache_and_no_fetch_skips(self, tmp_path):
        ctx = self._ctx(tmp_path, game_id="401603459", cache_dir=tmp_path / "pbp")
        pbp.run_stage(ctx)
        assert ctx.cache.read_json("pbp").get("skipped")

    def test_live_fetch_when_allowed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pbp, "fetch_game", lambda gid, lg: GAME)
        ctx = self._ctx(tmp_path, game_id="401603459", cache_dir=tmp_path / "pbp", allow_fetch=True)
        pbp.run_stage(ctx)
        out = ctx.cache.read_json("pbp")
        assert not out.get("skipped") and out["teams"]["home"]["key"] == "kansas-state"
