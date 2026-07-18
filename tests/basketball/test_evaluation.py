"""Unit tests for the eval matcher and scorers (libs/basketball/evaluation.py)."""

from pathlib import Path

import pytest

from libs.basketball.evaluation import (
    ClipTruth,
    GroundTruthEvent,
    Window,
    aggregate_scores,
    load_manifest,
    match_events,
    render_markdown,
    score_clip,
    time_gap,
)
from libs.basketball.timeline import Event

pytestmark = pytest.mark.unit

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "evals" / "basketball" / "datasets" / "manifest.yaml"

VERIFIED_ALL = {"event": True, "outcome": True, "team": True, "points": True, "jersey": True}


def shot(t, t_end=None, **kwargs) -> Event:
    return Event(t=t, t_end=t_end, type="shot", **kwargs)


def gt(t, t_end=None, verified=None, **kwargs) -> GroundTruthEvent:
    return GroundTruthEvent(event=shot(t, t_end, **kwargs), verified=verified or dict(VERIFIED_ALL))


class TestMatcher:
    def test_exact_match(self):
        matches, up, ut = match_events([shot(10.0)], [shot(10.0)], tolerance_sec=2.0)
        assert len(matches) == 1 and not up and not ut

    def test_one_second_off_matches(self):
        matches, up, ut = match_events([shot(11.0)], [shot(10.0)], tolerance_sec=2.0)
        assert len(matches) == 1
        assert matches[0][2] == pytest.approx(1.0)

    def test_three_seconds_off_does_not_match(self):
        matches, up, ut = match_events([shot(13.0)], [shot(10.0)], tolerance_sec=2.0)
        assert not matches and up == [0] and ut == [0]

    def test_duplicate_predictions_match_one_to_one(self):
        matches, up, ut = match_events([shot(10.0), shot(10.5)], [shot(10.0)], tolerance_sec=2.0)
        assert len(matches) == 1
        assert matches[0][0] == 0, "greedy: closest prediction wins"
        assert up == [1] and not ut

    def test_put_back_two_truths_in_one_window(self):
        # Two ground-truth events 1 s apart; two predictions -> both matched 1:1.
        matches, up, ut = match_events([shot(10.1), shot(11.2)], [shot(10.0), shot(11.0)], tolerance_sec=2.0)
        assert len(matches) == 2 and not up and not ut
        assert {(p, t) for p, t, _ in matches} == {(0, 0), (1, 1)}

    def test_point_inside_a_span_matches(self):
        # A point inside a [20, 30] span overlaps it -> gap 0, an exact match.
        matches, _, _ = match_events([shot(20.0, t_end=30.0)], [shot(24.0)], tolerance_sec=2.0)
        assert len(matches) == 1
        assert matches[0][2] == pytest.approx(0.0)

    def test_prediction_inside_wide_truth_window_matches(self):
        # Regression (shot_0090): ground-truth windows are uncertainty ranges,
        # not durations. A prediction at 21.5 sits inside the labelled 12-22 s
        # window and must be a true positive. Midpoint matching scored it 4.5 s
        # from the centre (17.0) and counted it as BOTH an FP and an FN.
        matches, up, ut = match_events([shot(21.5)], [shot(12.0, t_end=22.0)], tolerance_sec=2.0)
        assert len(matches) == 1 and not up and not ut
        assert matches[0][2] == pytest.approx(0.0)

    def test_prediction_just_outside_window_edge_still_within_tolerance(self):
        # 1 s past the window's edge -> inside the ±2 s tolerance.
        matches, _, _ = match_events([shot(23.0)], [shot(12.0, t_end=22.0)], tolerance_sec=2.0)
        assert len(matches) == 1
        assert matches[0][2] == pytest.approx(1.0)

    def test_prediction_beyond_tolerance_of_window_edge_does_not_match(self):
        # 3 s past the edge -> beyond tolerance. This is the shot_0017 case:
        # the tolerance must stay meaningful outside the window, otherwise a
        # genuinely wrong label would be silently "rescued".
        matches, up, ut = match_events([shot(25.0)], [shot(12.0, t_end=22.0)], tolerance_sec=2.0)
        assert not matches and up == [0] and ut == [0]

    def test_two_predictions_in_one_window_match_closest_centre(self):
        # Both gap 0.0; the tie breaks toward the closest midpoint (17.0).
        matches, up, ut = match_events([shot(13.0), shot(17.5)], [shot(12.0, t_end=22.0)], tolerance_sec=2.0)
        assert len(matches) == 1 and ut == []
        assert matches[0][0] == 1, "tie at gap 0 breaks toward the closest midpoint"
        assert up == [0]


class TestTimeGap:
    def test_points_reduce_to_absolute_distance(self):
        assert time_gap(shot(10.0), shot(13.5)) == pytest.approx(3.5)

    def test_overlapping_spans_are_zero(self):
        assert time_gap(shot(12.0, t_end=22.0), shot(21.5)) == pytest.approx(0.0)
        assert time_gap(shot(10.0, t_end=20.0), shot(15.0, t_end=25.0)) == pytest.approx(0.0)

    def test_disjoint_spans_measure_edge_distance(self):
        assert time_gap(shot(10.0, t_end=20.0), shot(23.0)) == pytest.approx(3.0)
        assert time_gap(shot(30.0), shot(10.0, t_end=20.0)) == pytest.approx(10.0)

    def test_symmetric(self):
        a, b = shot(10.0, t_end=20.0), shot(26.0)
        assert time_gap(a, b) == pytest.approx(time_gap(b, a))


class TestScoreClip:
    def test_empty_predictions_recall_zero(self):
        truth = ClipTruth(name="c", events=[gt(10.0), gt(20.0)])
        score = score_clip(truth, [], tolerance_sec=2.0)
        assert score.tp == 0 and score.fn == 2 and score.fp == 0
        assert score.recall == 0.0

    def test_perfect_predictions(self):
        truth = ClipTruth(name="c", events=[gt(10.0, team="kansas", points=2, jersey="4")])
        preds = [shot(10.0, team="kansas", points=2, jersey="4")]
        score = score_clip(truth, preds, tolerance_sec=2.0)
        assert score.precision == 1.0 and score.recall == 1.0 and score.f1 == 1.0
        assert score.attributes["team"].accuracy == 1.0
        assert score.attributes["points"].accuracy == 1.0
        assert score.attributes["jersey"].accuracy == 1.0

    def test_attribute_scoring_only_on_matched(self):
        truth = ClipTruth(name="c", events=[gt(10.0, team="kansas"), gt(25.0, team="kansas-state")])
        preds = [shot(10.0, team="kansas-state")]  # matches first truth only, wrong team
        score = score_clip(truth, preds, tolerance_sec=2.0)
        assert score.tp == 1 and score.fn == 1
        assert score.attributes["team"].total == 1, "unmatched truth must not count toward attributes"
        assert score.attributes["team"].correct == 0

    def test_jersey_compared_as_string(self):
        truth = ClipTruth(name="c", events=[gt(10.0, jersey="04")])
        score = score_clip(truth, [shot(10.0, jersey="04")], tolerance_sec=2.0)
        assert score.attributes["jersey"].correct == 1

    def test_unverified_event_excluded_by_default(self):
        unverified = GroundTruthEvent(event=shot(10.0), verified={k: False for k in VERIFIED_ALL})
        truth = ClipTruth(name="c", events=[unverified])
        score = score_clip(truth, [], tolerance_sec=2.0)
        assert score.truth_count == 0 and score.fn == 0

    def test_prediction_on_unverified_event_ignored_not_fp(self):
        unverified = GroundTruthEvent(event=shot(10.0), verified={k: False for k in VERIFIED_ALL})
        truth = ClipTruth(name="c", events=[unverified])
        score = score_clip(truth, [shot(10.5)], tolerance_sec=2.0)
        assert score.fp == 0 and score.ignored == 1

    def test_include_unverified_scores_everything(self):
        unverified = GroundTruthEvent(event=shot(10.0, team="kansas"), verified={k: False for k in VERIFIED_ALL})
        truth = ClipTruth(name="c", events=[unverified])
        score = score_clip(truth, [shot(10.0, team="kansas")], tolerance_sec=2.0, include_unverified=True)
        assert score.tp == 1 and score.recall == 1.0
        assert score.attributes["team"].correct == 1

    def test_unverified_attribute_not_scored_by_default(self):
        event = GroundTruthEvent(
            event=shot(10.0, team="kansas-state", jersey="4"),
            verified={"event": True, "outcome": True, "team": False, "points": False, "jersey": True},
        )
        truth = ClipTruth(name="shot_0029", events=[event])
        score = score_clip(truth, [shot(10.0, team="kansas", jersey="4")], tolerance_sec=2.0)
        assert score.attributes["jersey"].total == 1 and score.attributes["jersey"].correct == 1
        assert score.attributes["team"].total == 0, "unverified attribute must not be scored"

    def test_no_scoring_window_made_prediction_is_fp(self):
        truth = ClipTruth(name="shot_0020", no_scoring=[Window(clip="shot_0020", t=15.0, t_end=22.0, verified=True)])
        score = score_clip(truth, [shot(18.0, outcome="made")], tolerance_sec=2.0)
        assert score.fp == 1
        assert len(score.assertion_violations) == 1
        assert "no-scoring window" in score.assertion_violations[0]

    def test_no_scoring_window_miss_prediction_ignored(self):
        # The window asserts only that no basket was MADE; a predicted miss
        # claims no points, so it is unadjudicated -> ignored, not a false
        # positive and not a violation (the shot_0083 case).
        truth = ClipTruth(name="shot_0083", no_scoring=[Window(clip="shot_0083", t=15.0, t_end=22.0, verified=True)])
        score = score_clip(truth, [shot(18.0, outcome="missed")], tolerance_sec=2.0)
        assert score.fp == 0 and score.ignored == 1
        assert not score.assertion_violations

    def test_no_scoring_window_clean_pass(self):
        truth = ClipTruth(name="shot_0020", no_scoring=[Window(clip="shot_0020", t=15.0, t_end=22.0, verified=True)])
        score = score_clip(truth, [], tolerance_sec=2.0)
        assert score.assertion_checks == 1 and not score.assertion_violations

    def test_needs_review_window_ignores_unmatched_predictions(self):
        truth = ClipTruth(name="c", needs_review=[Window(clip="c", t=20.0, t_end=30.0)])
        score = score_clip(truth, [shot(25.0)], tolerance_sec=2.0)
        assert score.fp == 0 and score.ignored == 1

    def test_whole_clip_needs_review_ignores_everything(self):
        truth = ClipTruth(name="shot_0030", needs_review=[Window(clip="shot_0030")])
        score = score_clip(truth, [shot(5.0), shot(25.0)], tolerance_sec=2.0)
        assert score.fp == 0 and score.ignored == 2

    def test_non_scoring_prediction_types_excluded(self):
        truth = ClipTruth(name="c", events=[gt(10.0)])
        preds = [Event(t=10.0, type="score_change")]
        score = score_clip(truth, preds, tolerance_sec=2.0)
        assert score.pred_count == 0 and score.fn == 1


class TestAggregateAndReport:
    def test_aggregate_sums(self):
        a = score_clip(ClipTruth(name="a", events=[gt(10.0)]), [shot(10.0)], 2.0)
        b = score_clip(ClipTruth(name="b", events=[gt(5.0)]), [], 2.0)
        total = aggregate_scores([a, b])
        assert total.tp == 1 and total.fn == 1
        assert total.recall == 0.5

    def test_markdown_table(self):
        scores = [score_clip(ClipTruth(name="a", events=[gt(10.0)]), [shot(10.0)], 2.0)]
        text = render_markdown(scores, include_unverified=False, tolerance_sec=2.0)
        assert "| Clip |" in text and "| a |" in text and "**TOTAL**" in text


class TestManifest:
    def test_load_committed_manifest(self):
        manifest = load_manifest(MANIFEST_PATH)
        assert len(manifest.clips) == 22
        assert manifest.tolerance_sec == 2.0

        shot_0013 = manifest.clips["shot_0013"]
        assert shot_0013.events[0].event.type == "free_throw"
        assert shot_0013.events[0].verified["event"] is True

        # Scoreboard relabel: shot_0029 is kansas +2 at ~2s (team/points now
        # confirmed), not the original KSU jersey-4 @22-30 (jersey dropped).
        shot_0029 = manifest.clips["shot_0029"]
        assert shot_0029.events[0].verified == {
            "event": True,
            "outcome": True,
            "team": True,
            "points": True,
            "jersey": False,
        }
        # Scoreboard relabel: shot_0094 is a 3-pointer (41-32 -> 41-35), not a 2.
        assert manifest.clips["shot_0094"].events[0].event.points == 3

        shot_0099 = manifest.clips["shot_0099"]
        assert shot_0099.events[0].points_attempted == 3
        assert shot_0099.events[0].event.points is None

        no_scoring_clips = {w.clip for c in manifest.clips.values() for w in c.no_scoring}
        assert no_scoring_clips == {"shot_0020", "shot_0069", "shot_0083"}
        review_clips = {w.clip for c in manifest.clips.values() for w in c.needs_review}
        assert review_clips == {"shot_0071", "shot_0075", "shot_0078", "shot_0082"}

    def test_ground_truth_as_predictions_is_perfect(self):
        """run_eval acceptance: GT fed back as predictions => P = R = 1.0."""
        manifest = load_manifest(MANIFEST_PATH)
        scores = []
        for clip in manifest.clips.values():
            preds = [g.event for g in clip.events if g.verified.get("event")]
            scores.append(score_clip(clip, preds, manifest.tolerance_sec))
        total = aggregate_scores(scores)
        assert total.tp > 0
        assert total.precision == 1.0 and total.recall == 1.0
        assert not total.assertion_violations
        for attribute in ("team", "points", "jersey"):
            stat = total.attributes[attribute]
            assert stat.total == 0 or stat.accuracy == 1.0

    def test_empty_predictions_report_recall_zero(self):
        manifest = load_manifest(MANIFEST_PATH)
        scores = [score_clip(clip, [], manifest.tolerance_sec) for clip in manifest.clips.values()]
        total = aggregate_scores(scores)
        assert total.tp == 0 and total.fn == total.truth_count and total.recall == 0.0
        render_markdown(scores, include_unverified=False, tolerance_sec=manifest.tolerance_sec)  # must not crash
