"""Unit tests for the shots stage (libs/basketball/shots.py).

Synthetic trajectories are written directly into fake detect arrays (the
detect-stage contract) and classified via the pure ``analyze`` core; cut
detection and ``run_stage`` are exercised against tiny PyAV-encoded clips.
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from libs.basketball import shots
from libs.basketball.cache import ClipCache
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import StageContext

FPS = 8.0
DT = 1.0 / FPS
# Rim: plane y = 90, full x-range [150, 190], inner x-range [158, 182],
# neighborhood (3x) x [110, 230] y [60, 120], miss proximity (1.5x)
# x [140, 200] y [75, 105].
RIM_BOX = (150.0, 80.0, 190.0, 100.0)


def settings(**overrides) -> BasketballSettings:
    return BasketballSettings(**overrides)


class DetBuilder:
    """Builds detect-stage arrays.npz content (see libs/basketball/detect.py)."""

    def __init__(self, n_frames: int = 80, fps: float = FPS):
        self.frame_t = np.arange(n_frames, dtype=np.float64) / fps
        self._rows = []  # (class_id, fidx, box, score)

    def add(
        self, class_id: int, fidx: int, cx: float, cy: float, w: float = 10.0, h: float = 10.0, score: float = 0.9
    ) -> int:
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        self._rows.append((class_id, fidx, box, score))
        return len(self._rows) - 1

    def add_box(self, class_id: int, fidx: int, box, score: float = 0.9) -> int:
        self._rows.append((class_id, fidx, list(box), score))
        return len(self._rows) - 1

    def add_rims(self, box=RIM_BOX, step: int = 4, score: float = 0.9) -> None:
        for fidx in range(0, len(self.frame_t), step):
            self.add_box(shots.CLASS_RIM, fidx, box, score)

    def build(self) -> dict:
        n = len(self._rows)
        return {
            "boxes": np.array([r[2] for r in self._rows], dtype=np.float32).reshape(n, 4),
            "scores": np.array([r[3] for r in self._rows], dtype=np.float32),
            "class_ids": np.array([r[0] for r in self._rows], dtype=np.int32),
            "frame_idx": np.array([r[1] for r in self._rows], dtype=np.int32),
            "frame_t": self.frame_t,
        }


def add_make_arc(b: DetBuilder, fidx0: int) -> list:
    """Clean make: approach, above plane in rim x-range, through inner rim."""
    return [
        b.add(shots.CLASS_BALL, fidx0, 120, 72),
        b.add(shots.CLASS_BALL, fidx0 + 1, 168, 75),  # above plane, in [150, 190]
        b.add(shots.CLASS_BALL, fidx0 + 2, 171, 104),  # below plane, in [158, 182]
        b.add(shots.CLASS_BALL, fidx0 + 3, 170, 118),
    ]


def add_rollout_arc(b: DetBuilder, fidx0: int) -> list:
    """Front-rim roll-out: dips below the plane OUTSIDE the inner x-range."""
    return [
        b.add(shots.CLASS_BALL, fidx0, 152, 78),  # above plane, in full x-range
        b.add(shots.CLASS_BALL, fidx0 + 1, 150, 98),  # below plane, x=150 outside inner
        b.add(shots.CLASS_BALL, fidx0 + 2, 140, 112),  # rolls away
    ]


def analyze(b: DetBuilder, cuts=(), **setting_overrides):
    return shots.analyze(b.build(), list(cuts), settings(**setting_overrides))


@pytest.mark.unit
class TestTrajectoryClassification:
    def test_clean_make(self):
        b = DetBuilder()
        b.add_rims()
        rows = add_make_arc(b, 10)
        result = analyze(b)
        assert len(result["shot_candidates"]) == 1
        cand = result["shot_candidates"][0]
        assert cand["kind"] == "make"
        assert cand["trajectory_kind"] == "make"
        assert cand["signals"] == ["trajectory"]
        # crossing between the above sample (t=11*DT) and below sample (t=12*DT)
        assert 11 * DT < cand["t_rim"] < 12 * DT
        assert cand["t"] == cand["t_rim"]
        assert cand["confidence"] >= 0.85
        assert set(rows) <= set(cand["det_rows"])
        assert cand["window"][0] == pytest.approx(10 * DT, abs=1e-3)
        assert cand["suppressed"] is False and cand["possible_replay"] is False
        # last ball position before the crossing = the above-plane sample
        assert cand["last_ball"]["center"] == [168.0, 75.0]

    def test_front_rim_rollout_is_miss_never_make(self):
        b = DetBuilder()
        b.add_rims()
        add_rollout_arc(b, 10)
        result = analyze(b)
        kinds = [c["kind"] for c in result["shot_candidates"]]
        assert kinds == ["miss"]
        assert result["shot_candidates"][0]["t_rim"] is None

    def test_airball_is_miss(self):
        b = DetBuilder()
        b.add_rims()
        # Falls past the rim plane inside the neighborhood, left of the rim.
        b.add(shots.CLASS_BALL, 10, 118, 70)
        b.add(shots.CLASS_BALL, 11, 116, 95)
        b.add(shots.CLASS_BALL, 12, 114, 112)
        result = analyze(b)
        assert [c["kind"] for c in result["shot_candidates"]] == ["miss"]

    def test_flat_pass_is_unknown(self):
        b = DetBuilder()
        b.add_rims()
        # Crosses the neighborhood below the rim, never above the plane and
        # never inside the miss-proximity box: not shot-like.
        for i, x in enumerate((115, 145, 175, 205, 225)):
            b.add(shots.CLASS_BALL, 10 + i, x, 112)
        result = analyze(b)
        assert [c["kind"] for c in result["shot_candidates"]] == ["unknown"]

    def test_slow_free_throw_drop_is_make(self):
        b = DetBuilder()
        b.add_rims()
        for i, (x, y) in enumerate(((170, 76), (170, 79), (170, 82), (171, 85), (170, 88), (170, 97))):
            b.add(shots.CLASS_BALL, 10 + i, x, y)
        result = analyze(b)
        cand = result["shot_candidates"][0]
        assert cand["kind"] == "make"
        assert cand["confidence"] >= 0.85  # slow approach must not be penalized

    def test_occlusion_gap_still_make(self):
        b = DetBuilder()
        b.add_rims()
        b.add(shots.CLASS_BALL, 9, 120, 72)
        b.add(shots.CLASS_BALL, 10, 168, 75)  # above plane
        # frames 11-12 missing: ball hidden by rim/net
        b.add(shots.CLASS_BALL, 13, 170, 104)  # below plane, inner range
        result = analyze(b)
        cand = result["shot_candidates"][0]
        assert cand["kind"] == "make"
        assert 10 * DT < cand["t_rim"] < 13 * DT
        assert cand["confidence"] < 0.9  # gap costs confidence vs a clean make

    def test_gap_beyond_tolerance_splits_episode_no_make(self):
        b = DetBuilder()
        b.add_rims()
        b.add(shots.CLASS_BALL, 9, 120, 72)
        b.add(shots.CLASS_BALL, 10, 168, 75)
        # 4 missing samples > shots_gap_max_samples=3 -> episode splits
        b.add(shots.CLASS_BALL, 15, 170, 104)
        b.add(shots.CLASS_BALL, 16, 170, 116)
        result = analyze(b)
        assert result["shot_candidates"]
        assert all(c["kind"] != "make" for c in result["shot_candidates"])

    def test_nearest_player_hint(self):
        b = DetBuilder()
        b.add_rims()
        add_make_arc(b, 10)
        near = b.add(shots.CLASS_PLAYER, 11, 200, 140, w=30, h=60)
        b.add(shots.CLASS_PLAYER, 11, 60, 220, w=30, h=60)  # far player
        result = analyze(b)
        assert result["shot_candidates"][0]["nearest_player_det_row"] == near


@pytest.mark.unit
class TestRims:
    def test_no_rims_no_candidates(self):
        b = DetBuilder()
        add_make_arc(b, 10)  # ball flies but there is no rim anywhere
        result = analyze(b)
        assert result["rims"] == []
        assert result["shot_candidates"] == []

    def test_rim_cluster_below_min_dets_dropped(self):
        b = DetBuilder()
        b.add_box(shots.CLASS_RIM, 0, RIM_BOX)  # a single spurious rim det
        result = analyze(b)
        assert result["rims"] == []

    def test_two_rims_and_ball_assignment(self):
        far_rim = (450.0, 80.0, 490.0, 100.0)
        b = DetBuilder()
        b.add_rims(RIM_BOX)
        b.add_rims(far_rim)
        add_make_arc(b, 10)  # at RIM_BOX only
        result = analyze(b)
        assert len(result["rims"]) == 2
        left = min(result["rims"], key=lambda r: r["box"][0])
        cands = result["shot_candidates"]
        assert len(cands) == 1
        assert cands[0]["rim_id"] == left["rim_id"]

    def test_rim_box_is_median_of_jittered_dets(self):
        b = DetBuilder()
        rng = np.random.default_rng(7)
        for fidx in range(0, 40, 2):
            jitter = rng.uniform(-2, 2, size=4)
            b.add_box(shots.CLASS_RIM, fidx, np.asarray(RIM_BOX) + jitter)
        result = analyze(b)
        assert len(result["rims"]) == 1
        assert np.allclose(result["rims"][0]["box"], RIM_BOX, atol=2.5)


@pytest.mark.unit
class TestBallInBasket:
    def test_bib_merges_into_make_candidate(self):
        b = DetBuilder()
        b.add_rims()
        add_make_arc(b, 10)
        bib = b.add(shots.CLASS_BALL_IN_BASKET, 12, 170, 95, score=0.95)
        result = analyze(b)
        assert len(result["shot_candidates"]) == 1
        cand = result["shot_candidates"][0]
        assert cand["signals"] == ["trajectory", "ball_in_basket"]
        assert cand["kind"] == "make"
        assert bib in cand["det_rows"]
        assert cand["confidence"] >= 0.9

    def test_bib_upgrades_miss_to_make(self):
        b = DetBuilder()
        b.add_rims()
        add_rollout_arc(b, 10)
        b.add(shots.CLASS_BALL_IN_BASKET, 11, 170, 95, score=0.95)
        result = analyze(b)
        cand = result["shot_candidates"][0]
        assert cand["kind"] == "make"
        assert cand["trajectory_kind"] == "miss"  # geometry verdict preserved
        assert set(cand["signals"]) == {"trajectory", "ball_in_basket"}

    def test_standalone_bib_candidate(self):
        b = DetBuilder()
        b.add_rims()
        b.add(shots.CLASS_BALL_IN_BASKET, 20, 170, 95, score=0.9)
        b.add(shots.CLASS_BALL_IN_BASKET, 21, 170, 96, score=0.7)
        result = analyze(b)
        assert len(result["shot_candidates"]) == 1
        cand = result["shot_candidates"][0]
        assert cand["kind"] == "make"
        assert cand["trajectory_kind"] is None
        assert cand["signals"] == ["ball_in_basket"]
        assert cand["t"] == pytest.approx(20 * DT, abs=1e-3)  # highest-score det
        assert cand["rim_id"] == 0


@pytest.mark.unit
class TestReplayGuard:
    def test_candidate_spanning_cut_suppressed(self):
        b = DetBuilder()
        for fidx in range(0, 10, 2):  # rim only before the cut
            b.add_box(shots.CLASS_RIM, fidx, RIM_BOX)
        add_make_arc(b, 9)  # window [9, 12] * DT spans the cut at 1.3 s
        result = analyze(b, cuts=[1.3])
        assert len(result["shot_candidates"]) == 1
        assert result["shot_candidates"][0]["suppressed"] is True

    def test_replay_in_other_segment_flagged_not_dropped(self):
        b = DetBuilder()
        b.add_rims()
        add_make_arc(b, 10)  # t ~1.3 s, segment 0
        add_make_arc(b, 30)  # t ~3.8 s, segment 1 — same-kind repeat
        result = analyze(b, cuts=[2.5])
        cands = sorted(result["shot_candidates"], key=lambda c: c["t"])
        assert len(cands) == 2
        assert cands[0]["possible_replay"] is False
        assert cands[1]["possible_replay"] is True
        assert cands[1]["suppressed"] is False
        assert [c["segment"] for c in cands] == [0, 1]

    def test_same_segment_candidates_not_flagged(self):
        b = DetBuilder()
        b.add_rims()
        add_make_arc(b, 10)
        add_make_arc(b, 30)
        result = analyze(b)  # no cuts: both in segment 0
        assert all(c["possible_replay"] is False for c in result["shot_candidates"])


# ---------------------------------------------------------------------------
# Video-backed tests: cut detection + run_stage
# ---------------------------------------------------------------------------

WIDTH, HEIGHT, RATE = 320, 240, 30


def write_clip(path: Path, color_segments) -> Path:
    """Encode solid-color segments [(duration_sec, (b, g, r)), ...]."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=RATE)
    stream.width, stream.height = WIDTH, HEIGHT
    stream.pix_fmt = "yuv420p"
    pts = 0
    for duration, bgr in color_segments:
        img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        img[:] = bgr
        for _ in range(int(round(duration * RATE))):
            frame = av.VideoFrame.from_ndarray(img[:, :, ::-1], format="rgb24")
            frame.pts = pts
            frame.time_base = Fraction(1, RATE)
            pts += 1
            for packet in stream.encode(frame):
                container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return path


@pytest.mark.unit
class TestDetectCuts:
    def test_hard_cut_found(self, tmp_path):
        clip = write_clip(tmp_path / "cut.mp4", [(4.0, (30, 60, 200)), (4.0, (200, 60, 30))])
        cuts = shots.detect_cuts(clip, FPS, 0.5)
        assert len(cuts) == 1
        assert cuts[0] == pytest.approx(4.0, abs=0.3)

    def test_constant_clip_has_no_cuts(self, tmp_path):
        clip = write_clip(tmp_path / "flat.mp4", [(4.0, (30, 60, 200))])
        assert shots.detect_cuts(clip, FPS, 0.5) == []


@pytest.mark.unit
class TestRunStage:
    def _context(self, tmp_path, clip: Path, builder: DetBuilder) -> StageContext:
        cache = ClipCache(tmp_path / "work", "clip-abc12345")
        cache.write_arrays("detect", builder.build())
        cache.write_json(
            "detect",
            {
                "clip_id": "clip-abc12345",
                "model": {"classes": ["ball", "rim", "ball_in_basket", "player", "number", "referee"]},
                "npz": "arrays.npz",
            },
        )
        return StageContext(
            stage="shots",
            clip_path=clip,
            clip_id="clip-abc12345",
            settings=settings(),
            cache=cache,
            force=False,
        )

    def test_run_stage_writes_output(self, tmp_path):
        clip = write_clip(tmp_path / "clip.mp4", [(6.0, (30, 60, 200))])
        b = DetBuilder(n_frames=48)
        b.add_rims()
        add_make_arc(b, 10)
        ctx = self._context(tmp_path, clip, b)
        shots.run_stage(ctx)
        assert ctx.cache.is_warm("shots")
        out = ctx.cache.read_json("shots")
        assert out["clip_id"] == "clip-abc12345"
        assert out["cuts"] == []
        assert len(out["shot_candidates"]) == 1
        assert out["shot_candidates"][0]["kind"] == "make"
        assert out["rims"] and out["segments"]

    def test_run_stage_warm_skip_and_force(self, tmp_path):
        clip = write_clip(tmp_path / "clip.mp4", [(6.0, (30, 60, 200))])
        b = DetBuilder(n_frames=48)
        b.add_rims()
        ctx = self._context(tmp_path, clip, b)
        shots.run_stage(ctx)
        marker = ctx.cache.path("shots", "output.json")
        first = marker.stat().st_mtime_ns
        shots.run_stage(ctx)  # warm -> no rewrite
        assert marker.stat().st_mtime_ns == first
        ctx.force = True
        shots.run_stage(ctx)
        assert marker.stat().st_mtime_ns >= first

    def test_run_stage_requires_detect_cache(self, tmp_path):
        clip = write_clip(tmp_path / "clip.mp4", [(2.0, (30, 60, 200))])
        cache = ClipCache(tmp_path / "work", "clip-abc12345")
        ctx = StageContext(
            stage="shots", clip_path=clip, clip_id="clip-abc12345", settings=settings(), cache=cache, force=False
        )
        with pytest.raises(FileNotFoundError):
            shots.run_stage(ctx)
