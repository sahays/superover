"""Unit tests for the fact-constrained Gemini narration stage (Epic 4, story 2).

Everything here runs with a mocked analyzer — no network, no google-genai
import, no GCP env. The real ``SceneAnalyzer`` is only reached through the
lazily-imported ``narrate._make_analyzer``, which these tests monkeypatch.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

import libs.basketball.narrate as narrate
from libs.basketball.cache import ClipCache
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import StageContext
from libs.basketball.timeline import Event, predictions_to_dict

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "basketball_analyze.py"


# --- Fixtures / helpers -------------------------------------------------------


def make_events():
    """Three events exercising every attribute combination (incl. nulls)."""
    return [
        Event(
            t=3.2,
            t_end=4.0,
            type="shot",
            outcome="made",
            team="home",
            points=2,
            jersey="23",
            confidence={"overall": 0.9},
            evidence=["trajectory", "score_delta"],
        ),
        Event(t=11.0, type="free_throw", outcome="missed", team="away"),
        Event(t=18.5, type="score_change", team="home", points=3),
    ]


def compliant_entries():
    """A canned Gemini response whose echoes match make_events() exactly."""
    return [
        {
            "timestamp_range": "3.2s-4.0s",
            "event_title": "Layup drops for the home side",
            "analysis": "Off a quick drive, number 23 finishes at the rim.",
            "category": "Shot",
            "echo": {"t": 3.2, "outcome": "made", "team": "home", "points": 2, "jersey": "23"},
        },
        {
            "timestamp_range": "11.0s",
            "event_title": "Free throw rims out",
            "analysis": "The away team's attempt from the line is no good.",
            "category": "Free Throw",
            "echo": {"t": 11.0, "outcome": "missed", "team": "away", "points": None, "jersey": None},
        },
        {
            "timestamp_range": "18.5s",
            "event_title": "Home side adds three",
            "analysis": "The scoreboard ticks up three for the home team.",
            "category": "Score Change",
            "echo": {"t": 18.5, "outcome": None, "team": "home", "points": 3, "jersey": None},
        },
    ]


def analyzer_response(entries, tokens=100, cost=0.001):
    """Shape a response the way SceneAnalyzer returns a top-level-array schema:
    the parsed-list metadata attach fails internally, so the JSON text lands
    under ``raw_response``."""
    return {
        "raw_response": json.dumps(entries),
        "parse_error": "list indices must be integers or slices, not str",
        "finish_reason": "STOP",
        "token_usage": {
            "prompt_tokens": tokens // 2,
            "candidates_tokens": tokens - tokens // 2,
            "total_tokens": tokens,
            "estimated_cost_usd": cost,
        },
        "chunk_index": 0,
        "chunk_duration": 18.5,
    }


class FakeAnalyzer:
    """Scripted stand-in for SceneAnalyzer; records every call."""

    model_name = "fake-gemini"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def analyze_chunk(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def make_ctx(tmp_path, clip: Path, **settings_overrides) -> StageContext:
    settings = BasketballSettings(workdir=str(tmp_path / "work"), **settings_overrides)
    clip_id = "clip-00000000"
    return StageContext(
        stage="narrate",
        clip_path=clip,
        clip_id=clip_id,
        settings=settings,
        cache=ClipCache(settings.workdir, clip_id),
    )


def seed_fuse(ctx: StageContext, events) -> None:
    ctx.cache.write_json("fuse", predictions_to_dict(ctx.clip_id, events))


@pytest.fixture
def dummy_clip(tmp_path) -> Path:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"\x00" * 16)  # never decoded: the analyzer is mocked
    return path


# --- Fact block ----------------------------------------------------------------


@pytest.mark.unit
class TestFactBlock:
    GOLDEN = (
        "Event 1 | t=3.2s-4.0s | type=shot | outcome=made | team=home | points=2 | jersey=23\n"
        "Event 2 | t=11.0s | type=free_throw | outcome=missed | team=away\n"
        "Event 3 | t=18.5s | type=score_change | team=home | points=3"
    )

    def test_golden_fact_block(self):
        assert narrate.build_fact_block(make_events()) == self.GOLDEN

    def test_null_attributes_omitted(self):
        block = narrate.build_fact_block(make_events())
        line2 = block.splitlines()[1]
        assert "points=" not in line2 and "jersey=" not in line2
        line3 = block.splitlines()[2]
        assert "outcome=" not in line3 and "jersey=" not in line3

    def test_stable_ordering_regardless_of_input_order(self):
        events = make_events()
        assert narrate.build_fact_block(list(reversed(events))) == self.GOLDEN

    def test_prompt_embeds_fact_block_and_rules(self):
        prompt = narrate.build_prompt(make_events())
        assert self.GOLDEN in prompt
        assert "EXACTLY 3 entries" in prompt
        assert "NEVER invent" in prompt
        assert "REJECTED" not in prompt

    def test_prompt_appends_violations_on_retry(self):
        prompt = narrate.build_prompt(make_events(), violations=["entry 1: echo.jersey='32' != verified jersey='23'"])
        assert "PREVIOUS ATTEMPT WAS REJECTED" in prompt
        assert "echo.jersey='32'" in prompt


# --- Validator -------------------------------------------------------------------


@pytest.mark.unit
class TestValidator:
    def test_compliant_response_accepted(self):
        assert narrate.validate_entries(compliant_entries(), make_events()) == []

    def test_wrong_jersey_is_violation(self):
        entries = copy.deepcopy(compliant_entries())
        entries[0]["echo"]["jersey"] = "32"
        violations = narrate.validate_entries(entries, make_events())
        assert len(violations) == 1
        assert "jersey" in violations[0] and "entry 1" in violations[0]

    def test_extra_entry_is_violation(self):
        entries = compliant_entries() + [
            {
                "timestamp_range": "25.0s",
                "event_title": "Invented",
                "analysis": "x",
                "category": "Shot",
                "echo": {"t": 25.0},
            }
        ]
        violations = narrate.validate_entries(entries, make_events())
        assert any("entry count 4 != verified event count 3" in v for v in violations)

    def test_missing_entry_is_violation(self):
        violations = narrate.validate_entries(compliant_entries()[:2], make_events())
        assert any("entry count 2 != verified event count 3" in v for v in violations)

    def test_t_off_by_3s_is_violation(self):
        entries = copy.deepcopy(compliant_entries())
        entries[0]["echo"]["t"] = 6.2
        violations = narrate.validate_entries(entries, make_events())
        assert len(violations) == 1
        assert "echo.t" in violations[0]

    def test_t_off_by_1s_is_ok(self):
        entries = copy.deepcopy(compliant_entries())
        entries[0]["echo"]["t"] = 4.2
        assert narrate.validate_entries(entries, make_events()) == []

    def test_wrong_team_and_points_flagged(self):
        entries = copy.deepcopy(compliant_entries())
        entries[2]["echo"]["team"] = "away"
        entries[2]["echo"]["points"] = 2
        violations = narrate.validate_entries(entries, make_events())
        assert len(violations) == 2
        assert any("echo.team" in v for v in violations)
        assert any("echo.points" in v for v in violations)

    def test_null_timeline_attrs_are_not_checked(self):
        # Event 2 has null points/jersey; whatever is echoed there is unchecked.
        entries = copy.deepcopy(compliant_entries())
        entries[1]["echo"]["jersey"] = "7"
        assert narrate.validate_entries(entries, make_events()) == []

    def test_missing_echo_object_is_violation(self):
        entries = copy.deepcopy(compliant_entries())
        del entries[0]["echo"]
        violations = narrate.validate_entries(entries, make_events())
        assert any("missing 'echo'" in v for v in violations)

    def test_unparseable_response_is_violation(self):
        violations = narrate.validate_entries(None, make_events())
        assert violations == ["response did not contain a parseable list of narration entries"]


# --- Response extraction ----------------------------------------------------------


@pytest.mark.unit
class TestExtractEntries:
    def test_raw_response_json_list(self):
        assert narrate.extract_entries(analyzer_response(compliant_entries())) == compliant_entries()

    def test_direct_entries_key(self):
        assert narrate.extract_entries({"entries": compliant_entries()}) == compliant_entries()

    def test_blocked_response(self):
        assert narrate.extract_entries({"blocked": True, "summary": "Analysis blocked"}) is None

    def test_truncated_json(self):
        assert narrate.extract_entries({"raw_response": '[{"timestamp_range": "3.2'}) is None


# --- run_stage flows ---------------------------------------------------------------


@pytest.mark.unit
class TestRunStage:
    def test_disabled_gating_writes_marker_and_never_builds_analyzer(self, tmp_path, dummy_clip, monkeypatch):
        def boom(_settings):
            raise AssertionError("analyzer must not be constructed when narration is disabled")

        monkeypatch.setattr(narrate, "_make_analyzer", boom)
        ctx = make_ctx(tmp_path, dummy_clip)  # narrate_enabled defaults to False
        assert ctx.settings.narrate_enabled is False
        narrate.run_stage(ctx)
        assert ctx.cache.read_json("narrate") == {"narrated": False, "reason": "disabled"}

    def test_happy_path_first_attempt_accepted(self, tmp_path, dummy_clip, monkeypatch):
        fake = FakeAnalyzer([analyzer_response(compliant_entries(), tokens=120, cost=0.002)])
        monkeypatch.setattr(narrate, "_make_analyzer", lambda _settings: fake)
        ctx = make_ctx(tmp_path, dummy_clip, narrate_enabled=True)
        seed_fuse(ctx, make_events())
        narrate.run_stage(ctx)

        output = ctx.cache.read_json("narrate")
        assert output["narrated"] is True
        assert output["model"] == "fake-gemini"
        assert output["fallback"] is False
        assert output["violations"] == []
        assert output["entries"] == compliant_entries()
        assert output["usage"] == {"tokens": 120, "estimated_cost_usd": 0.002}

        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["media_path"] == dummy_clip
        assert call["response_schema"] is narrate.RESPONSE_SCHEMA
        assert TestFactBlock.GOLDEN in call["prompt_text"]

    def test_retry_then_success(self, tmp_path, dummy_clip, monkeypatch):
        bad = copy.deepcopy(compliant_entries())
        bad[0]["echo"]["jersey"] = "32"
        fake = FakeAnalyzer(
            [
                analyzer_response(bad, tokens=100, cost=0.001),
                analyzer_response(compliant_entries(), tokens=110, cost=0.001),
            ]
        )
        monkeypatch.setattr(narrate, "_make_analyzer", lambda _settings: fake)
        ctx = make_ctx(tmp_path, dummy_clip, narrate_enabled=True)
        seed_fuse(ctx, make_events())
        narrate.run_stage(ctx)

        output = ctx.cache.read_json("narrate")
        assert output["fallback"] is False
        assert output["entries"] == compliant_entries()
        assert len(output["violations"]) == 1 and output["violations"][0].startswith("attempt 1:")
        assert output["usage"] == {"tokens": 210, "estimated_cost_usd": 0.002}
        assert len(fake.calls) == 2
        # The retry prompt carries the violations from the first attempt.
        assert "PREVIOUS ATTEMPT WAS REJECTED" in fake.calls[1]["prompt_text"]
        assert "jersey" in fake.calls[1]["prompt_text"]

    def test_retry_then_fallback(self, tmp_path, dummy_clip, monkeypatch):
        bad1 = copy.deepcopy(compliant_entries())
        bad1[0]["echo"]["jersey"] = "32"
        bad2 = copy.deepcopy(compliant_entries())
        bad2[2]["echo"]["t"] = 30.0
        fake = FakeAnalyzer([analyzer_response(bad1), analyzer_response(bad2)])
        monkeypatch.setattr(narrate, "_make_analyzer", lambda _settings: fake)
        ctx = make_ctx(tmp_path, dummy_clip, narrate_enabled=True)  # narrate_max_retries defaults to 1
        seed_fuse(ctx, make_events())
        narrate.run_stage(ctx)

        output = ctx.cache.read_json("narrate")
        assert output["fallback"] is True
        assert len(fake.calls) == 2
        assert [v.split(":")[0] for v in output["violations"]] == ["attempt 1", "attempt 2"]

        # Fallback entries are deterministic, one per event, facts echoed exactly.
        entries = output["entries"]
        assert len(entries) == 3
        assert narrate.validate_entries(entries, make_events()) == []
        assert entries[0]["echo"] == {"t": 3.2, "outcome": "made", "team": "home", "points": 2, "jersey": "23"}
        assert entries[0]["timestamp_range"] == "3.2s-4.0s"
        assert entries[0]["event_title"] == "Made 2-point shot"
        assert entries[0]["category"] == "Shot"
        assert entries[1]["event_title"] == "Missed free throw"
        assert entries[2]["category"] == "Score Change"
        assert "verified facts" in entries[0]["analysis"]

    def test_no_events_skips_gemini(self, tmp_path, dummy_clip, monkeypatch):
        def boom(_settings):
            raise AssertionError("analyzer must not be constructed for an empty timeline")

        monkeypatch.setattr(narrate, "_make_analyzer", boom)
        ctx = make_ctx(tmp_path, dummy_clip, narrate_enabled=True)
        seed_fuse(ctx, [])
        narrate.run_stage(ctx)
        output = ctx.cache.read_json("narrate")
        assert output["narrated"] is True
        assert output["entries"] == []
        assert output["fallback"] is False

    def test_missing_fuse_output_raises(self, tmp_path, dummy_clip):
        ctx = make_ctx(tmp_path, dummy_clip, narrate_enabled=True)
        with pytest.raises(FileNotFoundError, match="fuse"):
            narrate.run_stage(ctx)


# --- CLI wiring ---------------------------------------------------------------------


def load_cli():
    spec = importlib.util.spec_from_file_location("basketball_analyze_cli", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
class TestCliWiring:
    def test_parse_args_narrate_flag(self):
        cli = load_cli()
        assert cli.parse_args(["clip.mp4"]).narrate is False
        assert cli.parse_args(["clip.mp4", "--narrate"]).narrate is True

    def _run_main(self, cli, clip, tmp_path, monkeypatch, extra_args):
        captured = {}

        def fake_run_stage(ctx):
            captured["narrate_enabled"] = ctx.settings.narrate_enabled
            ctx.cache.write_json(ctx.stage, {"narrated": False, "reason": "test"})

        monkeypatch.setattr(narrate, "run_stage", fake_run_stage)
        # Run only the narrate stage: isolates the wiring under test from the
        # other pipeline stages (and their model/data prerequisites).
        monkeypatch.setattr(cli, "STAGE_ORDER", ["narrate"])
        rc = cli.main([str(clip), "--workdir", str(tmp_path / "work"), "-o", str(tmp_path / "out.json"), *extra_args])
        assert rc == 0
        assert "narrate_enabled" in captured, "narrate stage was never invoked"
        return captured["narrate_enabled"]

    def test_narrate_flag_flips_setting(self, dummy_clip, tmp_path, monkeypatch):
        cli = load_cli()
        assert self._run_main(cli, dummy_clip, tmp_path, monkeypatch, ["--narrate"]) is True

    def test_default_run_keeps_narration_disabled(self, dummy_clip, tmp_path, monkeypatch):
        cli = load_cli()
        assert self._run_main(cli, dummy_clip, tmp_path, monkeypatch, []) is False
