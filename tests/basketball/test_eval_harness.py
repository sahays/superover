"""Eval-marked tests: dataset integrity + reviewer-error regression assertions.

Run with: pytest tests/basketball -m eval
Skipped automatically when the (gitignored) eval clips are not downloaded —
run evals/basketball/build_dataset.py first.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.basketball.evaluation import load_manifest
from libs.basketball.stages import is_implemented
from libs.basketball.timeline import SCORING_EVENT_TYPES, predictions_from_dict

pytestmark = pytest.mark.eval

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS = REPO_ROOT / "evals" / "basketball" / "datasets"
CLIPS_DIR = DATASETS / "clips"
MANIFEST = DATASETS / "manifest.yaml"
CLI = REPO_ROOT / "scripts" / "basketball_analyze.py"


def downloaded_clips():
    if not CLIPS_DIR.is_dir():
        return []
    return sorted(CLIPS_DIR.glob("shot_*.mp4"))


def require_clips():
    clips = downloaded_clips()
    if not clips:
        pytest.skip(f"eval clips not present under {CLIPS_DIR} — run evals/basketball/build_dataset.py")
    return clips


def run_pipeline(clip_path: Path, workdir: Path) -> dict:
    out = workdir / f"{clip_path.stem}.pred.json"
    result = subprocess.run(
        [sys.executable, str(CLI), str(clip_path), "-o", str(out), "--workdir", str(workdir)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(out.read_text())


class TestDatasetIntegrity:
    def test_manifest_covers_all_downloaded_clips(self):
        clips = require_clips()
        manifest = load_manifest(MANIFEST)
        for clip in clips:
            assert clip.stem in manifest.clips, f"{clip.stem} missing from manifest.yaml"

    def test_checksums_match(self):
        clips = require_clips()
        manifest = load_manifest(MANIFEST)
        checked = 0
        for clip in clips:
            expected = manifest.clips[clip.stem].sha256
            if not expected:
                continue
            actual = hashlib.sha256(clip.read_bytes()).hexdigest()
            assert actual == expected, f"checksum mismatch for {clip.name}"
            checked += 1
        if not checked:
            pytest.skip("no checksums recorded yet — run build_dataset.py")


class TestCliOnRealClip:
    def test_cli_end_to_end(self, tmp_path):
        clips = require_clips()
        data = run_pipeline(clips[0], tmp_path)
        assert "clip_id" in data and isinstance(data["events"], list)


# Reviewer-flagged errors the pipeline must fix (see story-2-eval-dataset.md).
# Each entry: clip name -> (description, predicate over the predicted events).
# Active once the 'fuse' stage exists; until then these skip.


def _events_in(events, t0, t1, **attrs):
    found = []
    for e in events:
        t = e.midpoint
        if not (t0 <= t <= t1):
            continue
        if all(getattr(e, k) == v for k, v in attrs.items()):
            found.append(e)
    return found


REGRESSIONS = {
    "shot_0013": (
        "no made free throw at 21-26 (Hunter misses the shot)",
        lambda ev: not _events_in(ev, 21, 26, type="free_throw", outcome="made"),
    ),
    "shot_0017": (
        "3PT at 10-17 credited to kansas",
        lambda ev: _events_in(ev, 10, 17, outcome="made", team="kansas", points=3),
    ),
    "shot_0020": (
        "no scoring event in 15-22",
        lambda ev: not [e for e in _events_in(ev, 15, 22) if e.type in SCORING_EVENT_TYPES],
    ),
    "shot_0024": (
        "make at 0-6 scored as 2PT, not 3PT",
        lambda ev: _events_in(ev, 0, 6, outcome="made", points=2) and not _events_in(ev, 0, 6, points=3),
    ),
    "shot_0028": (
        "scoring event detected at 21-29",
        lambda ev: _events_in(ev, 21, 29, outcome="made"),
    ),
    "shot_0029": (
        "scorer at 22-30 wears jersey #4",
        lambda ev: _events_in(ev, 22, 30, outcome="made", jersey="4"),
    ),
}


class TestReviewerRegressions:
    @pytest.mark.parametrize("clip_name", sorted(REGRESSIONS))
    def test_flagged_error_is_fixed(self, clip_name, tmp_path):
        if not is_implemented("fuse"):
            pytest.skip("fuse stage not implemented yet (Epic 2+) — regression checks inactive")
        require_clips()
        clip_path = CLIPS_DIR / f"{clip_name}.mp4"
        if not clip_path.is_file():
            pytest.skip(f"{clip_path.name} not downloaded")
        description, predicate = REGRESSIONS[clip_name]
        _clip_id, events = predictions_from_dict(run_pipeline(clip_path, tmp_path))
        assert predicate(events), f"{clip_name}: regression — expected {description}"
