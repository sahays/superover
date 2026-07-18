"""Tests for the fuse stage (libs/basketball/timeline.py fuse_signals/run_stage).

Covers the fusion truth table (every {trajectory, ball_in_basket, delta}
combination), cluster->team resolution voting, jersey attachment, graceful
degradation with missing upstream stages, and a synthetic full-pipeline
integration run (fake detect cache + directly written scorebug/teams/jersey
fixture caches).
"""

import numpy as np
import pytest

from libs.basketball import shots, timeline
from libs.basketball.cache import ClipCache
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import StageContext, run_stage_by_name
from libs.basketball.timeline import fuse_signals

from tests.basketball.test_shots import RIM_BOX, DetBuilder, add_make_arc, add_rollout_arc, write_clip

CLIP_ID = "clip-abc12345"


# --- fixture builders (upstream stage output contracts) ---


def cand(
    kind="make", t=5.0, t_rim=5.0, signals=("trajectory",), suppressed=False, replay=False, row=None, cid=0, segment=0
):
    return {
        "candidate_id": cid,
        "kind": kind,
        "trajectory_kind": kind if "trajectory" in signals else None,
        "signals": list(signals),
        "t": t,
        "t_rim": t_rim,
        "window": [t - 0.4, t + 0.4],
        "segment": segment,
        "rim_id": 0,
        "confidence": 0.9,
        "det_rows": [],
        "last_ball": {"t": t - 0.1, "center": [168.0, 75.0], "det_row": 0},
        "nearest_player_det_row": row,
        "suppressed": suppressed,
        "possible_replay": replay,
    }


def shots_out(*cands, cuts=()):
    return {
        "clip_id": CLIP_ID,
        "fps_estimate": 8.0,
        "cuts": list(cuts),
        "segments": [[0.0, 30.0]],
        "rims": [{"rim_id": 0, "segment": 0, "box": list(RIM_BOX), "n_dets": 10, "t_first": 0.0, "t_last": 29.0}],
        "shot_candidates": list(cands),
        "params": {},
    }


def delta(t=5.4, points=2, team="kansas", side="left", conf=0.9, resync=False, t_end=None):
    return {
        "raw_t": round(t + 1.5, 3),
        "t": t,
        "t_end": t_end,
        "side": side,
        "team_abbr": "KU" if side == "left" else "KSU",
        "team": team,
        "delta": points,
        "score_after": [37, 51],
        "confidence": conf,
        "resync": resync,
    }


def sb_out(*events, bug_found=True, fields=True):
    return {
        "clip_id": CLIP_ID,
        "bug_found": bug_found,
        "score_fields_found": fields,
        "ocr_fps": 2.0,
        "lag_sec": 1.5,
        "roi": [8, 306, 624, 48] if bug_found else None,
        "fields": None,
        "reads": [],
        "events": list(events),
        "events_typed": [],
        "resync_count": sum(1 for e in events if e.get("resync")),
    }


def track(tid, cluster, rows, conf=0.9):
    return {
        "track_id": tid,
        "cluster": cluster,
        "cluster_confidence": conf,
        "det_rows": rows,
        "t_start": 0.0,
        "t_end": 30.0,
    }


def teams_out(*tracks):
    return {
        "clip_id": CLIP_ID,
        "n_tracks": len(tracks),
        "tracks": list(tracks),
        "cluster_stats": {"silhouette": 0.4, "method": "hsv-kmeans"},
    }


def jrec(tid, jersey, conf=0.8, n=4):
    return {"track_id": tid, "jersey": jersey, "confidence": conf, "n_reads": n, "votes": {str(jersey): n}}


def jersey_out(*recs):
    return {"clip_id": CLIP_ID, "tracks": list(recs)}


def feat(number, name="KALUMA", t_start=24.0, t_end=28.0, n_frames=10, conf=0.99):
    return {
        "number": number,
        "name": name,
        "t_start": t_start,
        "t_end": t_end,
        "n_frames": n_frames,
        "confidence": conf,
    }


def scorer_out(*features):
    return {"clip_id": CLIP_ID, "features": list(features)}


def aseg(t, text):
    return {"t_start": t, "t_end": t + 2.0, "text": text}


def acue(t, kind):
    return {"t": t, "kind": kind, "phrase": kind}


def asr_out(segments=(), cues=()):
    return {"clip_id": CLIP_ID, "segments": list(segments), "cues": list(cues)}


def one_event(events):
    assert len(events) == 1, [e.to_dict() for e in events]
    return events[0]


# --- Fusion truth table ---


@pytest.mark.unit
class TestFusionTruthTable:
    def test_make_bib_delta_is_triple_signal_make(self):
        events, _ = fuse_signals(shots_out(cand(signals=("trajectory", "ball_in_basket"))), sb_out(delta()))
        e = one_event(events)
        assert (e.type, e.outcome, e.points) == ("shot", "made", 2)
        assert e.t == 5.0  # rule 2: timestamp from t_rim, not the OCR delta
        assert e.evidence == ["trajectory", "ball_in_basket", "scorebug"]
        assert e.confidence["overall"] == pytest.approx(0.93)
        assert e.team == "kansas"

    def test_make_delta_is_double_signal_make(self):
        events, _ = fuse_signals(shots_out(cand()), sb_out(delta()))
        e = one_event(events)
        assert (e.type, e.outcome, e.points) == ("shot", "made", 2)
        assert e.evidence == ["trajectory", "scorebug"]
        assert e.confidence["overall"] == pytest.approx(0.85)

    def test_bib_only_delta_is_double_signal_make(self):
        events, _ = fuse_signals(
            shots_out(cand(kind="make", signals=("ball_in_basket",), t_rim=None, t=5.2)), sb_out(delta())
        )
        e = one_event(events)
        assert (e.outcome, e.points) == ("made", 2)
        assert e.t == 5.2  # bib detections carry their own t
        assert e.evidence == ["ball_in_basket", "scorebug"]
        assert e.confidence["overall"] == pytest.approx(0.85)

    def test_unknown_trajectory_delta_is_lower_confidence_make(self):
        events, _ = fuse_signals(shots_out(cand(kind="unknown", t_rim=None)), sb_out(delta()))
        e = one_event(events)
        assert e.outcome == "made"
        assert e.confidence["overall"] == pytest.approx(0.75)

    def test_delta_one_types_free_throw(self):
        events, _ = fuse_signals(shots_out(cand()), sb_out(delta(points=1)))
        e = one_event(events)
        assert (e.type, e.points) == ("free_throw", 1)

    def test_delta_three_types_shot(self):
        events, _ = fuse_signals(shots_out(cand()), sb_out(delta(points=3)))
        e = one_event(events)
        assert (e.type, e.points) == ("shot", 3)

    def test_make_without_delta_downgraded_to_miss(self):
        # Rule 3: the scorebug was watching and the score never moved.
        events, _ = fuse_signals(shots_out(cand()), sb_out())
        e = one_event(events)
        assert (e.type, e.outcome, e.points) == ("shot", "missed", None)
        assert e.evidence == ["trajectory"]
        assert e.confidence["overall"] == pytest.approx(0.55)

    def test_trajectory_miss_stays_miss(self):
        events, _ = fuse_signals(shots_out(cand(kind="miss", t_rim=None)), sb_out())
        e = one_event(events)
        assert (e.outcome, e.points) == ("missed", None)
        assert e.evidence == ["trajectory"]
        assert e.confidence["overall"] == pytest.approx(0.70)

    def test_miss_near_ocr_make_suppressed_as_same_shot(self):
        # A clean miss within MISS_ABSORB_WINDOW_SEC of a delta-confirmed
        # OCR-only make is the same shot the scoreboard confirmed (OCR lag put
        # the delta past confirm_window_sec): the phantom miss is dropped and
        # only the make survives, untouched (scorebug evidence, delta t/team).
        events, debug = fuse_signals(shots_out(cand(kind="miss", t_rim=None)), sb_out(delta()))
        e = one_event(events)
        assert (e.outcome, e.points, e.t) == ("made", 2, 5.4)
        assert e.evidence == ["scorebug"]
        assert any(d.get("reason") == "miss_shadowed_by_confirmed_make" for d in debug["dropped"])

    def test_miss_far_from_delta_kept_with_ocr_make(self):
        # Beyond the absorb window the delta belongs to some other undetected
        # make: the miss stays a miss AND the delta surfaces as an OCR-only
        # made event (two distinct events).
        events, _ = fuse_signals(shots_out(cand(kind="miss", t_rim=None)), sb_out(delta(t=15.0)))
        assert len(events) == 2
        miss, made = sorted(events, key=lambda e: e.t)
        assert (miss.outcome, miss.points) == ("missed", None)
        assert (made.outcome, made.points, made.t) == ("made", 2, 15.0)
        assert made.evidence == ["scorebug"]

    def test_delta_without_candidate_is_ocr_only_event(self):
        events, _ = fuse_signals(shots_out(), sb_out(delta(points=3, team="kansas-state", side="right")))
        e = one_event(events)
        assert (e.type, e.outcome, e.points, e.team) == ("shot", "made", 3, "kansas-state")
        assert e.t == 5.4  # scorebug t is already lag-adjusted
        assert e.evidence == ["scorebug"]
        assert e.confidence["overall"] <= 0.5

    def test_resync_delta_is_wide_window_score_change(self):
        events, _ = fuse_signals(shots_out(), sb_out(delta(t=17.0, points=2, resync=True, t_end=20.0)))
        e = one_event(events)
        assert (e.type, e.outcome, e.points) == ("score_change", None, None)
        assert (e.t, e.t_end) == (17.0, 20.0)
        assert e.confidence["overall"] == pytest.approx(0.30)
        assert e.evidence == ["scorebug"]

    def test_resync_catchup_delta_never_a_single_basket(self):
        events, _ = fuse_signals(shots_out(), sb_out(delta(t=17.0, points=5, resync=True, t_end=20.0)))
        e = one_event(events)
        assert (e.type, e.points) == ("score_change", None)

    def test_make_inside_resync_window_kept_as_unconfirmed_make(self):
        # The bug was hidden: absence of a per-basket delta is not informative.
        events, _ = fuse_signals(
            shots_out(cand(t=18.0, t_rim=18.0)),
            sb_out(delta(t=17.0, points=2, resync=True, t_end=20.0)),
        )
        assert len(events) == 2
        made = next(e for e in events if e.type == "shot")
        assert (made.outcome, made.points) == ("made", None)
        assert made.confidence["overall"] == pytest.approx(0.60)
        assert any(e.type == "score_change" for e in events)

    def test_unknown_without_delta_emits_nothing(self):
        events, _ = fuse_signals(shots_out(cand(kind="unknown", t_rim=None)), sb_out())
        assert events == []

    def test_replay_without_delta_dropped(self):
        events, debug = fuse_signals(shots_out(cand(replay=True)), sb_out())
        assert events == []
        assert any(d.get("reason") == "possible_replay" for d in debug["dropped"])

    def test_replay_with_own_delta_is_a_real_make(self):
        events, _ = fuse_signals(shots_out(cand(replay=True)), sb_out(delta()))
        e = one_event(events)
        assert (e.outcome, e.points) == ("made", 2)

    def test_suppressed_candidate_ignored(self):
        events, _ = fuse_signals(shots_out(cand(suppressed=True)), sb_out(delta()))
        e = one_event(events)  # only the OCR-only event survives
        assert e.evidence == ["scorebug"]
        assert e.t == 5.4

    def test_and_one_second_delta_becomes_free_throw_event(self):
        # +2 then +1 within seconds: the make consumes the FG delta, the
        # +1 surfaces as a separate OCR-only free throw.
        events, _ = fuse_signals(shots_out(cand()), sb_out(delta(t=5.4, points=2), delta(t=6.8, points=1)))
        assert len(events) == 2
        fg, ft = sorted(events, key=lambda e: e.t)
        assert (fg.type, fg.points) == ("shot", 2)
        assert (ft.type, ft.points, ft.evidence) == ("free_throw", 1, ["scorebug"])


@pytest.mark.unit
class TestShotType:
    """Epic-4 story-1: delta->type incl. and-one splitting and consecutive FTs."""

    def test_and_one_full_sequence_fg_then_three_fts(self):
        # make -> +2 (and-one +1 shortly after) -> later two consecutive FTs.
        events, _ = fuse_signals(
            shots_out(cand(t=5.0, t_rim=5.0)),
            sb_out(
                delta(t=5.4, points=2),
                delta(t=6.8, points=1),  # and-one bonus FT
                delta(t=15.0, points=1),  # consecutive FT pair
                delta(t=15.9, points=1),
            ),
        )
        assert len(events) == 4  # never merged
        fg, ft1, ft2, ft3 = sorted(events, key=lambda e: e.t)
        assert (fg.type, fg.points, fg.outcome, fg.t) == ("shot", 2, "made", 5.0)
        assert set(fg.evidence) == {"trajectory", "scorebug"}
        for ft, t_expected in ((ft1, 6.8), (ft2, 15.0), (ft3, 15.9)):
            assert (ft.type, ft.points, ft.outcome) == ("free_throw", 1, "made")
            assert ft.t == t_expected
            assert ft.evidence == ["scorebug"]

    def test_and_one_guard_fg_delta_wins_even_when_ft_is_closer(self):
        # Candidate between the deltas, nearer the +1: without the and-one
        # guard the FG would be typed free_throw and the +2 would float off
        # as a bogus OCR-only shot at the wrong time.
        events, _ = fuse_signals(
            shots_out(cand(t=6.0, t_rim=6.0)),
            sb_out(delta(t=5.4, points=2), delta(t=6.2, points=1)),
        )
        assert len(events) == 2
        fg = next(e for e in events if "trajectory" in e.evidence)
        assert (fg.type, fg.points, fg.t) == ("shot", 2, 6.0)
        ft = next(e for e in events if e.evidence == ["scorebug"])
        assert (ft.type, ft.points, ft.t) == ("free_throw", 1, 6.2)

    def test_ft_candidate_still_matches_the_and_one_delta(self):
        # Both the FG and the FT trajectories were detected: each confirms
        # against its own delta.
        events, _ = fuse_signals(
            shots_out(cand(t=5.0, t_rim=5.0, cid=0), cand(t=6.6, t_rim=6.6, cid=1)),
            sb_out(delta(t=5.4, points=2), delta(t=6.8, points=1)),
        )
        assert len(events) == 2
        fg, ft = sorted(events, key=lambda e: e.t)
        assert (fg.type, fg.points, fg.t) == ("shot", 2, 5.0)
        assert (ft.type, ft.points, ft.t) == ("free_throw", 1, 6.6)
        assert "trajectory" in ft.evidence and "scorebug" in ft.evidence

    def test_missed_shot_type_never_guessed_and_warned(self):
        events, debug = fuse_signals(shots_out(cand(kind="miss", t_rim=None)), sb_out())
        e = one_event(events)
        assert (e.type, e.outcome, e.points) == ("shot", "missed", None)
        assert any("homography deferred" in w for w in debug["warnings"])


# --- Free-throw scene corroboration (epic-4 story-1) ---


def ft_arrays(centers_by_frame, n_frames=240, fps=8.0):
    """Detect arrays for player boxes: {frame: [(cx, cy), ...]} -> arrays + det rows."""
    b = DetBuilder(n_frames=n_frames, fps=fps)
    rows_by_player = {}
    for fidx in sorted(centers_by_frame):
        for player, (cx, cy) in enumerate(centers_by_frame[fidx]):
            row = b.add(shots.CLASS_PLAYER, fidx, cx, cy, w=30, h=60)
            rows_by_player.setdefault(player, []).append(row)
    return b.build(), rows_by_player


def ft_tracks(rows_by_player):
    return [track(tid + 1, None, rows, conf=0.0) for tid, rows in sorted(rows_by_player.items())]


RIMS = [{"rim_id": 0, "segment": 0, "box": list(RIM_BOX), "n_dets": 10, "t_first": 0.0, "t_last": 29.0}]


@pytest.mark.unit
class TestFtSceneCorroboration:
    """Thresholds under test (timeline.py): >= 4 near-static tracks (center
    travel <= 0.6 player heights) within +/- 3 s, clustered within 8
    rim-widths of one rim center. RIM_BOX center is (170, 90), width 40."""

    def lineup(self, n_players=5, move=0.0, offset=(0.0, 0.0)):
        # Players at frames 38..46 (t 4.75-5.75 around a 5.4 s delta).
        frames = range(38, 47, 2)
        centers = {}
        for step, fidx in enumerate(frames):
            centers[fidx] = [
                (200 + 25 * p + offset[0] + move * step, 200 + offset[1] + move * step) for p in range(n_players)
            ]
        return centers

    def corroborated(self, centers):
        arrays, rows_by_player = ft_arrays(centers)
        return timeline.ft_scene_corroborated(5.4, ft_tracks(rows_by_player), arrays, RIMS)

    def test_static_lineup_near_rim_corroborates(self):
        assert self.corroborated(self.lineup()) is True

    def test_running_players_do_not_corroborate(self):
        # 30 px per sample >> 0.6 * 60 px total-travel budget.
        assert self.corroborated(self.lineup(move=30.0)) is False

    def test_lineup_far_from_rim_does_not_corroborate(self):
        # 8 rim-widths = 320 px from rim center (170, 90).
        assert self.corroborated(self.lineup(offset=(900.0, 500.0))) is False

    def test_too_few_static_players(self):
        assert self.corroborated(self.lineup(n_players=3)) is False

    def test_missing_inputs_never_corroborate(self):
        arrays, rows_by_player = ft_arrays(self.lineup())
        tracks = ft_tracks(rows_by_player)
        assert timeline.ft_scene_corroborated(5.4, None, arrays, RIMS) is False
        assert timeline.ft_scene_corroborated(5.4, tracks, None, RIMS) is False
        assert timeline.ft_scene_corroborated(5.4, tracks, arrays, []) is False

    def test_ocr_only_ft_confidence_boosted_and_tagged(self):
        arrays, rows_by_player = ft_arrays(self.lineup())
        base_events, _ = fuse_signals(shots_out(), sb_out(delta(points=1)))
        boosted_events, _ = fuse_signals(
            shots_out(),
            sb_out(delta(points=1)),
            teams=teams_out(*ft_tracks(rows_by_player)),
            detect_arrays=arrays,
        )
        base, boosted = one_event(base_events), one_event(boosted_events)
        assert base.evidence == ["scorebug"]
        assert boosted.evidence == ["scorebug", "ft_scene"]
        assert boosted.confidence["overall"] > base.confidence["overall"]
        assert boosted.confidence["overall"] <= timeline.FT_SCENE_CONF_CAP

    def test_ocr_only_fg_never_gets_ft_scene_boost(self):
        arrays, rows_by_player = ft_arrays(self.lineup())
        events, _ = fuse_signals(
            shots_out(),
            sb_out(delta(points=2)),
            teams=teams_out(*ft_tracks(rows_by_player)),
            detect_arrays=arrays,
        )
        assert one_event(events).evidence == ["scorebug"]


@pytest.mark.unit
class TestConfidenceLadder:
    def test_ocr_only_lt_single_lt_multi(self):
        ocr_only, _ = fuse_signals(shots_out(), sb_out(delta()))
        single, _ = fuse_signals(shots_out(cand()), None)  # trajectory only
        double, _ = fuse_signals(shots_out(cand()), sb_out(delta()))
        triple, _ = fuse_signals(shots_out(cand(signals=("trajectory", "ball_in_basket"))), sb_out(delta()))
        values = [
            ocr_only[0].confidence["overall"],
            single[0].confidence["overall"],
            double[0].confidence["overall"],
            triple[0].confidence["overall"],
        ]
        assert values == sorted(values)
        assert len(set(values)) == 4  # strictly increasing


@pytest.mark.unit
class TestGracefulDegradation:
    def test_no_scorebug_output_trajectory_only_events(self):
        events, _ = fuse_signals(shots_out(cand(), cand(kind="miss", t_rim=None, t=9.0, cid=1)), None)
        assert len(events) == 2
        made, missed = sorted(events, key=lambda e: e.t)
        assert (made.outcome, made.points) == ("made", None)
        assert made.confidence["overall"] == pytest.approx(0.60)
        assert (missed.outcome, missed.confidence["overall"]) == ("missed", pytest.approx(0.65))

    def test_bug_not_found_same_as_absent(self):
        events, _ = fuse_signals(shots_out(cand()), sb_out(bug_found=False))
        assert one_event(events).outcome == "made"

    def test_score_fields_not_found_same_as_absent(self):
        events, _ = fuse_signals(shots_out(cand()), sb_out(fields=False))
        assert one_event(events).outcome == "made"

    def test_no_shots_output_ocr_only(self):
        events, _ = fuse_signals(None, sb_out(delta()))
        assert one_event(events).evidence == ["scorebug"]

    def test_nothing_upstream_empty_timeline(self):
        events, _ = fuse_signals(None, None)
        assert events == []

    def test_missing_teams_and_jersey_warned_and_null(self):
        events, debug = fuse_signals(shots_out(cand(row=100)), sb_out(delta()), teams=None, jersey=None)
        e = one_event(events)
        assert e.team == "kansas"  # scorebug only
        assert "teams" not in e.evidence and e.jersey is None
        assert len(debug["warnings"]) == 2


@pytest.mark.unit
class TestTeamResolution:
    def test_majority_vote_fixes_cluster_map_and_applies_to_all_events(self):
        shots_data = shots_out(
            cand(t=5.0, t_rim=5.0, row=100, cid=0),
            cand(t=12.0, t_rim=12.0, row=101, cid=1),
            cand(t=20.0, t_rim=20.0, row=102, cid=2),
            cand(kind="miss", t_rim=None, t=25.0, row=103, cid=3),
        )
        sb = sb_out(
            delta(t=5.4, team="kansas"),
            delta(t=12.4, team="kansas"),
            delta(t=20.4, team="kansas-state", side="right"),
        )
        teams = teams_out(
            track(1, 0, [100]),
            track(2, 0, [101]),
            track(3, 1, [102]),
            track(4, 1, [103]),
        )
        events, debug = fuse_signals(shots_data, sb, teams=teams)
        assert debug["cluster_to_team"] == {"0": "kansas", "1": "kansas-state"}
        by_t = {e.t: e for e in events}
        assert by_t[5.0].team == "kansas" and "teams" in by_t[5.0].evidence
        assert by_t[20.0].team == "kansas-state"
        # the miss has no delta: its team comes purely from the cluster map
        missed = by_t[25.0]
        assert (missed.outcome, missed.team) == ("missed", "kansas-state")
        assert "teams" in missed.evidence and "team" in missed.confidence

    def test_conflicting_vote_loses_to_majority(self):
        shots_data = shots_out(
            cand(t=5.0, t_rim=5.0, row=100, cid=0),
            cand(t=12.0, t_rim=12.0, row=101, cid=1),
            cand(t=20.0, t_rim=20.0, row=102, cid=2),
        )
        sb = sb_out(
            delta(t=5.4, team="kansas"),
            delta(t=12.4, team="kansas"),
            delta(t=20.4, team="kansas-state", side="right"),  # OCR mixed sides up
        )
        teams = teams_out(track(1, 0, [100]), track(2, 0, [101]), track(3, 0, [102]))
        events, debug = fuse_signals(shots_data, sb, teams=teams)
        assert debug["cluster_to_team"] == {"0": "kansas"}
        outlier = {e.t: e for e in events}[20.0]
        assert outlier.team == "kansas"  # the fixed map wins over its own delta
        assert outlier.confidence["team"] < 0.5
        # margin (2-1)/3 scales the winners' team confidence
        winner = {e.t: e for e in events}[5.0]
        assert winner.confidence["team"] == pytest.approx(0.5 + 0.4 / 3, abs=1e-3)

    def test_tied_votes_unresolved_team_from_scorebug_alone(self):
        shots_data = shots_out(cand(t=5.0, row=100, cid=0), cand(t=12.0, t_rim=12.0, row=101, cid=1))
        sb = sb_out(delta(t=5.4, team="kansas"), delta(t=12.4, team="kansas-state", side="right"))
        teams = teams_out(track(1, 0, [100]), track(2, 0, [101]))  # same cluster, 1:1 tie
        events, debug = fuse_signals(shots_data, sb, teams=teams)
        assert debug["cluster_to_team"] == {}
        for e in events:
            assert "teams" not in e.evidence
        assert {e.team for e in events} == {"kansas", "kansas-state"}

    def test_unclustered_track_never_votes(self):
        shots_data = shots_out(cand(t=5.0, row=100))
        events, debug = fuse_signals(shots_data, sb_out(delta()), teams=teams_out(track(1, None, [100])))
        assert debug["votes"] == []
        assert one_event(events).team == "kansas"  # scorebug fallback


@pytest.mark.unit
class TestJersey:
    def test_shooter_jersey_attached(self):
        events, _ = fuse_signals(
            shots_out(cand(row=100)),
            sb_out(delta()),
            teams=teams_out(track(1, 0, [100])),
            jersey=jersey_out(jrec(1, "24", conf=0.8)),
        )
        e = one_event(events)
        assert e.jersey == "24"
        assert e.confidence["jersey"] == pytest.approx(0.8)
        assert "jersey" in e.evidence

    def test_low_confidence_jersey_stays_null(self):
        events, _ = fuse_signals(
            shots_out(cand(row=100)),
            sb_out(delta()),
            teams=teams_out(track(1, 0, [100])),
            jersey=jersey_out(jrec(1, "24", conf=0.3)),
        )
        e = one_event(events)
        assert e.jersey is None and "jersey" not in e.evidence

    def test_jersey_applies_even_when_cluster_null(self):
        events, _ = fuse_signals(
            shots_out(cand(row=100)),
            sb_out(delta()),
            teams=teams_out(track(1, None, [100])),
            jersey=jersey_out(jrec(1, "10", conf=0.9)),
        )
        assert one_event(events).jersey == "10"


# --- run_stage: cache-backed behavior ---


@pytest.mark.unit
@pytest.mark.unit
class TestScorerGraphic:
    def test_graphic_jersey_attached_to_ocr_only_make(self):
        # The make is scoreboard-only (no shot candidate -> no shooter track),
        # yet the scorer lower-third supplies the jersey directly.
        events, _ = fuse_signals(shots_out(), sb_out(delta(t=25.0, points=2)), scorer=scorer_out(feat("24")))
        e = one_event(events)
        assert e.jersey == "24" and "scorer_graphic" in e.evidence

    def test_graphic_outside_window_not_attached(self):
        events, _ = fuse_signals(
            shots_out(), sb_out(delta(t=5.0, points=2)), scorer=scorer_out(feat("24", t_start=24.0, t_end=28.0))
        )
        assert one_event(events).jersey is None

    def test_ambiguous_scorers_leave_jersey_null(self):
        # Two different scorers equally present near one make -> prefer null.
        events, _ = fuse_signals(
            shots_out(),
            sb_out(delta(t=25.0, points=2)),
            scorer=scorer_out(feat("24", n_frames=10), feat("5", name="PERRY", n_frames=10)),
        )
        assert one_event(events).jersey is None

    def test_graphic_not_attached_to_a_miss(self):
        events, _ = fuse_signals(
            shots_out(cand(kind="miss", t_rim=None)), sb_out(), scorer=scorer_out(feat("24", t_start=4.0, t_end=8.0))
        )
        e = one_event(events)
        assert e.outcome == "missed" and e.jersey is None


@pytest.mark.unit
class TestAsrCorroboration:
    def test_scorer_name_cross_validated(self):
        # The graphic gives #2 TYLORPERRY; commentary says "Perry" -> the two
        # agree, so the make is tagged with asr evidence.
        events, _ = fuse_signals(
            shots_out(),
            sb_out(delta(t=25.0, points=2)),
            scorer=scorer_out(feat("2", name="TYLORPERRY", t_start=24.0, t_end=28.0)),
            asr=asr_out(segments=[aseg(24.0, "Tyler Perry drives and finishes")]),
        )
        e = one_event(events)
        assert e.jersey == "2" and "asr" in e.evidence

    def test_unrelated_commentary_not_cross_validated(self):
        events, _ = fuse_signals(
            shots_out(),
            sb_out(delta(t=25.0, points=2)),
            scorer=scorer_out(feat("2", name="TYLORPERRY", t_start=24.0, t_end=28.0)),
            asr=asr_out(segments=[aseg(24.0, "a look at the standings tonight")]),
        )
        assert "asr" not in one_event(events).evidence

    def test_make_outcome_corroborated_by_cue(self):
        events, _ = fuse_signals(shots_out(), sb_out(delta(t=25.0, points=2)), asr=asr_out(cues=[acue(25.0, "make")]))
        assert "asr" in one_event(events).evidence

    def test_skipped_asr_is_ignored(self):
        events, _ = fuse_signals(
            shots_out(), sb_out(delta(t=25.0, points=2)), asr={"skipped": True, "reason": "no deps"}
        )
        assert "asr" not in one_event(events).evidence


class TestFuseRunStage:
    def _context(self, tmp_path) -> StageContext:
        return StageContext(
            stage="fuse",
            clip_path=tmp_path / "clip.mp4",  # fuse never decodes video
            clip_id=CLIP_ID,
            settings=BasketballSettings(),
            cache=ClipCache(tmp_path / "work", CLIP_ID),
            force=False,
        )

    def test_output_is_predictions_format(self, tmp_path):
        ctx = self._context(tmp_path)
        ctx.cache.write_json("shots", shots_out(cand()))
        ctx.cache.write_json("scorebug", sb_out(delta()))
        timeline.run_stage(ctx)
        assert ctx.cache.is_warm("fuse")
        raw = ctx.cache.read_json("fuse")
        assert set(raw) == {"clip_id", "events"}
        clip_id, events = timeline.predictions_from_dict(raw)
        assert clip_id == CLIP_ID
        e = one_event(events)
        assert (e.type, e.outcome, e.points) == ("shot", "made", 2)
        # debug artifact exists and is not the warm marker
        assert ctx.cache.path("fuse", "fusion_debug.json").is_file()

    def test_missing_upstream_graceful(self, tmp_path):
        ctx = self._context(tmp_path)  # nothing cached at all
        timeline.run_stage(ctx)
        _clip_id, events = timeline.predictions_from_dict(ctx.cache.read_json("fuse"))
        assert events == []

    def test_scorebug_only(self, tmp_path):
        ctx = self._context(tmp_path)
        ctx.cache.write_json("scorebug", sb_out(delta()))
        timeline.run_stage(ctx)
        _clip_id, events = timeline.predictions_from_dict(ctx.cache.read_json("fuse"))
        assert one_event(events).evidence == ["scorebug"]

    def test_warm_skip_and_force(self, tmp_path):
        ctx = self._context(tmp_path)
        ctx.cache.write_json("shots", shots_out(cand()))
        timeline.run_stage(ctx)
        marker = ctx.cache.path("fuse", "output.json")
        first = marker.stat().st_mtime_ns
        timeline.run_stage(ctx)  # warm -> untouched
        assert marker.stat().st_mtime_ns == first
        ctx.force = True
        timeline.run_stage(ctx)


# --- Integration: full shots -> fuse over a synthetic clip + fixture caches ---


@pytest.mark.integration
class TestPipelineIntegration:
    def test_full_pipeline_synthetic_clip(self, tmp_path):
        # Clip: 24 s, hard camera cut at 12 s (color change).
        clip = write_clip(tmp_path / "game.mp4", [(12.0, (30, 60, 200)), (12.0, (200, 160, 30))])

        # Fake detect cache: rim throughout; live make ~5 s; front-rim miss
        # ~9 s; identical replay of the make at ~15 s (after the cut).
        b = DetBuilder(n_frames=192)  # 24 s at 8 fps
        b.add_rims()
        add_make_arc(b, 39)  # crossing ~5.06 s
        add_rollout_arc(b, 72)  # miss ~9.1 s
        add_make_arc(b, 120)  # replay ~15.1 s, segment 1
        shooter_row = b.add(shots.CLASS_PLAYER, 40, 200, 140, w=30, h=60)

        cache = ClipCache(tmp_path / "work", CLIP_ID)
        cache.write_arrays("detect", b.build())
        classes = ["ball", "rim", "ball_in_basket", "player", "number", "referee"]
        cache.write_json("detect", {"clip_id": CLIP_ID, "model": {"classes": classes}, "npz": "arrays.npz"})

        # Scorebug fixture: +2 kansas confirming the live make; +3 with no
        # candidate late in the clip (off-screen putback).
        cache.write_json(
            "scorebug",
            sb_out(
                delta(t=5.4, points=2, team="kansas"),
                delta(t=22.0, points=3, team="kansas-state", side="right", conf=0.85),
            ),
        )
        cache.write_json("teams", teams_out(track(7, 0, [shooter_row])))
        cache.write_json("jersey", jersey_out(jrec(7, "24", conf=0.8)))

        settings = BasketballSettings()
        for stage in ("shots", "fuse"):
            ctx = StageContext(
                stage=stage, clip_path=clip, clip_id=CLIP_ID, settings=settings, cache=cache, force=False
            )
            run_stage_by_name(stage, ctx)

        shots_result = cache.read_json("shots")
        assert len(shots_result["cuts"]) == 1
        assert shots_result["cuts"][0] == pytest.approx(12.0, abs=0.3)
        by_kind = {}
        for c in shots_result["shot_candidates"]:
            by_kind.setdefault(c["kind"], []).append(c)
        assert len(by_kind["make"]) == 2 and len(by_kind["miss"]) == 1
        replays = [c for c in shots_result["shot_candidates"] if c["possible_replay"]]
        assert len(replays) == 1 and replays[0]["segment"] == 1

        clip_id, events = timeline.predictions_from_dict(cache.read_json("fuse"))
        assert clip_id == CLIP_ID
        assert [e.t for e in events] == sorted(e.t for e in events)
        assert len(events) == 3  # replay dropped

        made = events[0]
        assert (made.type, made.outcome, made.points) == ("shot", "made", 2)
        assert made.t == pytest.approx(5.06, abs=0.1)  # rim-crossing, not OCR t
        assert made.team == "kansas" and made.jersey == "24"
        assert set(made.evidence) == {"trajectory", "scorebug", "teams", "jersey"}

        missed = events[1]
        assert (missed.type, missed.outcome, missed.points) == ("shot", "missed", None)
        assert missed.t == pytest.approx(9.1, abs=0.2)
        assert missed.evidence == ["trajectory"]

        ocr_only = events[2]
        assert (ocr_only.type, ocr_only.outcome, ocr_only.points) == ("shot", "made", 3)
        assert (ocr_only.t, ocr_only.team) == (22.0, "kansas-state")
        assert ocr_only.evidence == ["scorebug"]
        assert ocr_only.confidence["overall"] < missed.confidence["overall"] < made.confidence["overall"]

        # numpy round-trip sanity: everything JSON-serializable
        assert isinstance(np.asarray(shots_result["cuts"]).tolist(), list)
