"""Tests for the scorebug stage (Epic 2 story 1 — score-bug OCR, Signal A).

Unit tests cover the pure smoothing/event logic; integration tests run the
full stage (RapidOCR included) against synthetic broadcast fixtures built by
tests/basketball/scorebug_fixtures.py. Run with the basketball venv:

    .venv-basketball/bin/python -m pytest tests/basketball/test_scorebug.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.basketball import scorebug, video
from libs.basketball.cache import compute_clip_id
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import make_context
from libs.basketball.timeline import EVENT_TYPE_SCORE_CHANGE, Event
from tests.basketball.scorebug_fixtures import HEIGHT, ScoreScript, default_script, write_scorebug_clip

REPO_ROOT = Path(__file__).resolve().parents[2]


def _times(n: int, dt: float = 0.5):
    return [i * dt for i in range(n)]


# ---------------------------------------------------------------------------
# Unit: smoothing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSmoothing:
    def test_absorbs_single_frame_misread(self):
        """A one-read 35->85->35 flicker (8<->3 confusion) never survives."""
        values = [35] * 5 + [85] + [35] * 5
        smoothed, _ = scorebug.smooth_series(values)
        assert smoothed == [35] * 11

    def test_accepts_persistent_change(self):
        values = [35] * 5 + [38] * 5
        smoothed, _ = scorebug.smooth_series(values)
        assert smoothed == [35] * 5 + [38] * 5

    def test_hidden_frames_stay_missing_and_do_not_vote(self):
        values = [54, 54, None, None, None, 56, 56]
        smoothed, _ = scorebug.smooth_series(values)
        assert smoothed == [54, 54, None, None, None, 56, 56]

    def test_winning_vote_confidence_is_mean_of_matching_reads(self):
        values = [35, 35, 85, 35, 35]
        confs = [0.9, 0.8, 0.4, 0.8, 0.9]
        smoothed, sm_conf = scorebug.smooth_series(values, confs)
        assert smoothed == [35] * 5
        assert sm_conf[2] == pytest.approx((0.9 + 0.8 + 0.8 + 0.9) / 4)


# ---------------------------------------------------------------------------
# Unit: event extraction (domain rules)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEventExtraction:
    def test_flicker_produces_no_event_end_to_end(self):
        raw = [35] * 10 + [85] + [35] * 10
        smoothed, confs = scorebug.smooth_series(raw)
        right = [50] * len(smoothed)
        events = scorebug.extract_score_events(_times(len(smoothed)), smoothed, right, confs)
        assert events == []

    def test_delta_classification_1_2_3(self):
        left = [10] * 4 + [11] * 4 + [13] * 4 + [16] * 4
        right = [50] * len(left)
        events = scorebug.extract_score_events(_times(len(left)), left, right)
        assert [e["delta"] for e in events] == [1, 2, 3]
        assert all(e["side"] == "left" and not e["resync"] for e in events)
        assert [e["score_after"] for e in events] == [[11, 50], [13, 50], [16, 50]]

    def test_impossible_jump_rebaselines_without_event(self):
        """+7 with the bug in vision is an OCR glitch: no event, new baseline."""
        left = [35] * 4 + [42] * 4 + [44] * 4
        events = scorebug.extract_score_events(_times(len(left)), left, [50] * len(left))
        assert [e["delta"] for e in events] == [2]
        assert events[0]["score_after"] == [44, 50]

    def test_negative_jump_rebaselines_without_event(self):
        left = [40] * 4 + [12] * 4 + [14] * 4
        events = scorebug.extract_score_events(_times(len(left)), left, [50] * len(left))
        assert [e["delta"] for e in events] == [2]
        assert events[0]["score_after"] == [14, 50]

    def test_lag_adjustment(self):
        left = [10] * 4 + [12] * 4  # transition read at t=2.0
        events = scorebug.extract_score_events(_times(len(left)), left, [50] * len(left), lag_sec=1.5)
        assert events[0]["raw_t"] == pytest.approx(2.0)
        assert events[0]["t"] == pytest.approx(0.5)

    def test_lag_adjustment_clamps_at_zero(self):
        left = [10] * 2 + [12] * 4  # transition read at t=1.0, lag 3.0
        events = scorebug.extract_score_events(_times(len(left)), left, [50] * len(left), lag_sec=3.0)
        assert events[0]["t"] == 0.0

    def test_gap_resync_small_delta_is_window_event(self):
        times = [0.0, 0.5, 1.0, 4.0, 4.5, 5.0]  # 3 s hole > gap_sec
        left = [50, 50, 50, 52, 52, 52]
        events = scorebug.extract_score_events(times, left, [10] * 6, gap_sec=2.0)
        assert len(events) == 1
        event = events[0]
        assert event["resync"] is True
        assert event["delta"] == 2
        assert event["t"] == pytest.approx(1.0)  # gap start (lag 0)
        assert event["t_end"] == pytest.approx(4.0)  # reappearance
        assert event["raw_t_start"] == pytest.approx(1.0)
        assert event["raw_t"] == pytest.approx(4.0)

    def test_gap_resync_catchup_has_lowest_confidence(self):
        times = [0.0, 0.5, 1.0, 4.0, 4.5, 5.0]
        small = scorebug.extract_score_events(times, [50, 50, 50, 52, 52, 52], [10] * 6, gap_sec=2.0)
        catchup = scorebug.extract_score_events(times, [50, 50, 50, 57, 57, 57], [10] * 6, gap_sec=2.0)
        in_vision = scorebug.extract_score_events(_times(8), [50] * 4 + [52] * 4, [10] * 8)
        assert catchup[0]["delta"] == 7
        assert catchup[0]["resync"] is True
        assert catchup[0]["confidence"] < small[0]["confidence"] < in_vision[0]["confidence"]

    def test_both_sides_tracked_independently(self):
        left = [10] * 4 + [12] * 8
        right = [50] * 8 + [53] * 4
        events = scorebug.extract_score_events(_times(len(left)), left, right)
        assert [(e["side"], e["delta"]) for e in events] == [("left", 2), ("right", 3)]
        assert events[1]["score_after"] == [12, 53]


# ---------------------------------------------------------------------------
# Unit: parsing and alias mapping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAliasMapping:
    @pytest.mark.parametrize(
        "abbr,team",
        [
            ("KU", "kansas"),
            ("kan", "kansas"),
            ("Kansas", "kansas"),
            ("K.U.", "kansas"),
            ("KSU", "kansas-state"),
            ("kst", "kansas-state"),
            ("K-State", "kansas-state"),
            ("KSTATE", "kansas-state"),
        ],
    )
    def test_known_aliases_map(self, abbr, team):
        assert scorebug.map_abbr_to_team(abbr) == team

    @pytest.mark.parametrize("abbr", ["UNC", "DUKE", "XYZ", "", None])
    def test_unknown_aliases_map_to_none(self, abbr):
        assert scorebug.map_abbr_to_team(abbr) is None


@pytest.mark.unit
class TestParsing:
    @pytest.mark.parametrize(
        "text,value",
        [("35", 35), (" 51 ", 51), ("S1", 51), ("3S", 35), ("0", 0), ("150", 150), ("1O7", 107)],
    )
    def test_parse_score_accepts(self, text, value):
        assert scorebug.parse_score(text) == value

    @pytest.mark.parametrize("text", ["12:34", "151", "abc", "", "-3", "3.5"])
    def test_parse_score_rejects(self, text):
        assert scorebug.parse_score(text) is None

    @pytest.mark.parametrize(
        "text,seconds",
        [("12:34", 754.0), ("12.34", 754.0), ("0:59", 59.0), ("1:05.4", 65.4)],
    )
    def test_parse_clock_accepts(self, text, seconds):
        assert scorebug.parse_clock(text) == pytest.approx(seconds)

    @pytest.mark.parametrize("text", ["1:75", "35", "abc", ""])
    def test_parse_clock_rejects(self, text):
        assert scorebug.parse_clock(text) is None


# ---------------------------------------------------------------------------
# Integration: full stage on synthetic broadcast fixtures (RapidOCR runs)
# ---------------------------------------------------------------------------


def _run_pipeline(clip: Path, workdir: Path) -> dict:
    clip_id = compute_clip_id(clip)
    settings = BasketballSettings(workdir=str(workdir))
    decode_ctx = make_context("decode", clip, clip_id, settings, workdir, force=True)
    video.run_stage(decode_ctx)
    ctx = make_context("scorebug", clip, clip_id, settings, workdir, force=True)
    scorebug.run_stage(ctx)
    assert ctx.cache.is_warm("scorebug")
    return ctx.cache.read_json("scorebug")


@pytest.fixture(scope="session")
def scripted_clip(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("scorebug-clips") / "scripted.mp4"
    return write_scorebug_clip(path, default_script())


@pytest.fixture(scope="session")
def scripted_output(scripted_clip, tmp_path_factory) -> dict:
    workdir = tmp_path_factory.mktemp("scorebug-work")
    return _run_pipeline(scripted_clip, workdir)


@pytest.mark.integration
class TestScorebugStageOnScriptedClip:
    """default_script(): KU 35->37 @ 8 s, KSU 51->54 @ 15 s, bug hidden
    17.5-20.5 s with KSU 54->56 during the hole, and a single-read 35->85
    flicker @ 5 s. Expected: exactly two precise events + one resync window."""

    def test_bug_and_fields_discovered(self, scripted_output):
        out = scripted_output
        assert out["bug_found"] is True
        assert out["score_fields_found"] is True
        x, y, w, h = out["roi"]
        assert y > 0.6 * HEIGHT  # bottom-strip bar, found not hardcoded
        assert w > 0 and h > 0
        assert out["fields"]["left"]["abbr"] == "KU"
        assert out["fields"]["left"]["team"] == "kansas"
        assert out["fields"]["right"]["abbr"] == "KSU"
        assert out["fields"]["right"]["team"] == "kansas-state"
        assert out["fields"]["clock"] is not None
        for side in ("left", "right"):
            fx, fy, fw, fh = out["fields"][side]["roi"]
            assert fx >= x and fy >= y and fx + fw <= x + w and fy + fh <= y + h

    def test_exactly_the_scripted_events(self, scripted_output):
        events = scripted_output["events"]
        assert len(events) == 3
        e1, e2, e3 = events

        assert (e1["side"], e1["delta"], e1["resync"]) == ("left", 2, False)
        assert e1["raw_t"] == pytest.approx(8.0, abs=1.0)
        assert e1["t"] == pytest.approx(6.5, abs=1.0)  # raw minus 1.5 s lag
        assert (e1["team_abbr"], e1["team"]) == ("KU", "kansas")
        assert e1["score_after"] == [37, 51]

        assert (e2["side"], e2["delta"], e2["resync"]) == ("right", 3, False)
        assert e2["raw_t"] == pytest.approx(15.0, abs=1.0)
        assert e2["t"] == pytest.approx(13.5, abs=1.0)
        assert (e2["team_abbr"], e2["team"]) == ("KSU", "kansas-state")
        assert e2["score_after"] == [37, 54]

        # The 54->56 change happened while the bug was hidden (17.5-20.5 s):
        # one resync window event spanning the hole, never a precise phantom.
        assert (e3["side"], e3["delta"], e3["resync"]) == ("right", 2, True)
        assert e3["raw_t_start"] == pytest.approx(17.0, abs=1.0)
        assert e3["raw_t"] == pytest.approx(20.5, abs=1.0)
        assert e3["raw_t_start"] <= 19.0 <= e3["raw_t"]  # true change inside window
        assert e3["t_end"] is not None and e3["t"] <= e3["t_end"]
        assert e3["score_after"] == [37, 56]
        assert e3["confidence"] < min(e1["confidence"], e2["confidence"])
        assert scripted_output["resync_count"] == 1

    def test_no_phantom_events(self, scripted_output):
        events = scripted_output["events"]
        # The 35->85 flicker at 5 s must not emit anything.
        assert not [e for e in events if e["raw_t"] < 7.0]
        # One left event total; right deltas sum to the scripted +5.
        assert sum(1 for e in events if e["side"] == "left") == 1
        assert sum(e["delta"] for e in events if e["side"] == "right") == 5

    def test_hidden_interval_reads_marked_invisible(self, scripted_output):
        reads = scripted_output["reads"]
        assert reads, "expected per-frame reads"
        hidden = [r for r in reads if 17.6 <= r["raw_t"] <= 20.4]
        assert hidden and all(r["visible"] is False for r in hidden)
        assert all(r[side] is None for r in hidden for side in ("left", "right", "clock"))
        early = [r for r in reads if r["raw_t"] < 17.0]
        assert early and all(r["visible"] is True for r in early)

    def test_events_typed_are_valid_timeline_events(self, scripted_output):
        events = scripted_output["events"]
        typed = scripted_output["events_typed"]
        assert len(typed) == len(events) == 3
        for raw, data in zip(events, typed):
            event = Event.from_dict(data)  # round-trips through the model
            assert event.type == EVENT_TYPE_SCORE_CHANGE
            assert event.evidence == ["scorebug"]
            assert event.t == pytest.approx(raw["t"])
            assert event.t_end == raw["t_end"] or event.t_end == pytest.approx(raw["t_end"])
            assert event.team == raw["team"]
            assert event.points == raw["delta"]  # all scripted deltas are <= 3
            assert event.confidence["overall"] == pytest.approx(raw["confidence"])


@pytest.mark.integration
def test_no_bug_clip_reports_bug_not_found(tmp_path_factory):
    path = tmp_path_factory.mktemp("scorebug-clips") / "nobug.mp4"
    write_scorebug_clip(path, ScoreScript(duration=6.0, show_bar=False))
    out = _run_pipeline(path, tmp_path_factory.mktemp("scorebug-work"))
    assert out["bug_found"] is False
    assert out["score_fields_found"] is False
    assert out["roi"] is None
    assert out["fields"] == {"left": None, "right": None, "clock": None}
    assert out["reads"] == []
    assert out["events"] == []
    assert out["events_typed"] == []


@pytest.mark.integration
def test_cli_runs_scorebug_stage(scripted_clip, tmp_path):
    workdir = tmp_path / "work"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "basketball_analyze.py"),
        str(scripted_clip),
        "--stage",
        "scorebug",
        "--workdir",
        str(workdir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=280)
    assert proc.returncode == 0, proc.stderr
    clip_id = compute_clip_id(scripted_clip)
    output_path = workdir / clip_id / "scorebug" / "output.json"
    assert output_path.is_file()
    out = json.loads(output_path.read_text(encoding="utf-8"))
    assert out["bug_found"] is True
    assert len(out["events"]) == 3
    # The CLI still prints the (empty until 'fuse' lands) predictions JSON.
    printed = json.loads(proc.stdout)
    assert printed["clip_id"] == clip_id
