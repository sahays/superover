"""Unit tests for the stage registry contract and the decode stage; plus CLI integration."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.basketball.cache import ClipCache, compute_clip_id
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import (
    STAGE_ORDER,
    STAGE_REGISTRY,
    StageContext,
    is_implemented,
    resolve_stage,
    run_stage_by_name,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "basketball_analyze.py"


def make_ctx(stage: str, clip: Path, workdir: Path, **settings_overrides) -> StageContext:
    settings = BasketballSettings(workdir=str(workdir), **settings_overrides)
    clip_id = compute_clip_id(clip)
    return StageContext(
        stage=stage,
        clip_path=clip,
        clip_id=clip_id,
        settings=settings,
        cache=ClipCache(workdir, clip_id),
    )


@pytest.mark.unit
class TestRegistry:
    def test_all_planned_stages_registered(self):
        expected = ["decode", "scorebug", "detect", "shots", "teams", "jersey", "fuse", "narrate"]
        assert STAGE_ORDER == expected
        assert set(STAGE_REGISTRY) == set(expected)

    def test_lazy_import_paths_shape(self):
        for name, target in STAGE_REGISTRY.items():
            module, attr = target.split(":")
            assert module.startswith("libs.basketball."), name
            assert attr == "run_stage"

    def test_unknown_stage_raises_keyerror(self):
        with pytest.raises(KeyError, match="Unknown stage"):
            resolve_stage("rebound")

    def test_unimplemented_stage_raises_not_implemented(self, monkeypatch):
        # All 8 real stages are implemented now; exercise the registry's
        # NotImplementedError paths with temporary fake entries.
        monkeypatch.setitem(STAGE_REGISTRY, "future", "libs.basketball.does_not_exist:run_stage")
        with pytest.raises(NotImplementedError, match="future"):
            resolve_stage("future")
        assert not is_implemented("future")
        # Module exists but exposes no run_stage attribute.
        monkeypatch.setitem(STAGE_REGISTRY, "future2", "libs.basketball.cache:run_stage")
        with pytest.raises(NotImplementedError, match="future2"):
            resolve_stage("future2")
        assert not is_implemented("future2")

    def test_all_registered_stages_are_implemented(self):
        for name in STAGE_ORDER:
            assert is_implemented(name), name
            assert callable(resolve_stage(name))


@pytest.mark.unit
class TestDecodeStage:
    def test_decode_stage_writes_output(self, cfr_clip, tmp_path):
        ctx = make_ctx("decode", cfr_clip, tmp_path, base_fps=8.0)
        run_stage_by_name("decode", ctx)
        assert ctx.cache.is_warm("decode")
        output = ctx.cache.read_json("decode")
        assert output["clip_id"] == ctx.clip_id
        assert output["base_fps"] == 8.0
        assert output["probe"]["width"] == 320
        timestamps = output["frame_timestamps"]
        assert output["num_sampled_frames"] == len(timestamps) > 0
        assert all(b > a for a, b in zip(timestamps, timestamps[1:]))


@pytest.mark.integration
class TestCliIntegration:
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *[str(a) for a in args]],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )

    @pytest.fixture
    def clip_5s(self, tmp_path_factory):
        from tests.basketball.conftest import write_synthetic_clip

        path = tmp_path_factory.mktemp("cli") / "synthetic_5s.mp4"
        return write_synthetic_clip(path, list(range(150)))

    def test_end_to_end_produces_valid_json(self, clip_5s, tmp_path):
        # Default no-model run: detect degrades gracefully (skipped marker,
        # clear warning) and the pipeline still exits 0 with scorebug-only
        # fusion (here: no bug on the synthetic clip -> zero events).
        out = tmp_path / "out.json"
        result = self.run_cli(clip_5s, "-o", out, "--workdir", tmp_path / "work")
        assert result.returncode == 0, result.stderr
        data = json.loads(out.read_text())
        assert set(data) == {"clip_id", "events"}
        assert data["events"] == []
        assert "no detection model configured" in result.stderr  # graceful skip warned
        assert "not implemented" not in result.stderr  # every stage is implemented

    def test_second_run_uses_warm_cache(self, clip_5s, tmp_path):
        workdir = tmp_path / "work"
        first = self.run_cli(clip_5s, "--workdir", workdir)
        assert first.returncode == 0, first.stderr
        assert "cache is warm" not in first.stderr
        second = self.run_cli(clip_5s, "--workdir", workdir)
        assert second.returncode == 0, second.stderr
        assert "stage 'decode' cache is warm" in second.stderr

    def test_single_stage_rerun(self, clip_5s, tmp_path):
        workdir = tmp_path / "work"
        result = self.run_cli(clip_5s, "--workdir", workdir, "--stage", "decode")
        assert result.returncode == 0, result.stderr
        assert "stage 'decode' finished" in result.stderr

    def test_missing_clip_fails_cleanly(self, tmp_path):
        result = self.run_cli(tmp_path / "nope.mp4")
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_corrupt_clip_fails_cleanly(self, tmp_path):
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"garbage" * 1000)
        result = self.run_cli(bad, "--workdir", tmp_path / "work")
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_stage_detect_without_model_still_raises(self, clip_5s, tmp_path):
        # Graceful degradation is pipeline-only: an explicit --stage detect
        # invocation with no model keeps the instructive hard error.
        result = self.run_cli(clip_5s, "--workdir", tmp_path / "work", "--stage", "detect")
        assert result.returncode == 1
        assert "no detection model configured" in result.stderr
        assert "models/README.md" in result.stderr

    def test_narrate_without_gemini_deps_fails_actionably(self, clip_5s, tmp_path):
        # narrate IS implemented; in this venv the optional google-genai
        # dependencies are absent, so a --narrate run over a non-empty
        # timeline must exit 1 with an actionable error.
        workdir = tmp_path / "work"
        first = self.run_cli(clip_5s, "--workdir", workdir)
        assert first.returncode == 0, first.stderr
        cache = ClipCache(workdir, compute_clip_id(clip_5s))
        event = {"t": 1.0, "type": "shot", "outcome": "made", "points": 2}
        cache.write_json("fuse", {"clip_id": cache.clip_id, "events": [event]})
        result = self.run_cli(clip_5s, "--narrate", "--workdir", workdir)
        assert result.returncode == 1
        assert "--narrate needs the optional Gemini dependencies" in result.stderr

    def test_debug_video_renders_annotated_mp4(self, clip_5s, tmp_path):
        out = tmp_path / "out.json"
        result = self.run_cli(clip_5s, "-o", out, "--workdir", tmp_path / "work", "--debug-video")
        assert result.returncode == 0, result.stderr
        mp4 = tmp_path / "out.debug.mp4"
        assert mp4.is_file() and mp4.stat().st_size > 0
        import av

        with av.open(str(mp4)) as container:
            frames = sum(1 for _ in container.decode(video=0))
        assert frames > 0  # 5 s clip at 8 fps -> ~40 annotated frames
