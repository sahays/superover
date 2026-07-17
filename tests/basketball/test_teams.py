"""Tests for libs/basketball/teams.py (teams stage, Epic 3 story 1).

Unit tests cover the torso-crop geometry, the HSV kit-color feature, the
deterministic k=2 clustering (numbering, silhouette gate), referee exclusion,
tiny-track null, and the tracker reset at camera cuts. The integration test
renders a synthetic two-team clip (PyAV, like conftest.py) with a scripted
fake detect cache and runs the real stage end to end.

Run with: .venv-basketball/bin/python -m pytest tests/basketball/test_teams.py -v
"""

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import av
import numpy as np
import pytest

from libs.basketball import teams
from libs.basketball.cache import ClipCache, compute_clip_id
from libs.basketball.config import BasketballSettings
from libs.basketball.stages import StageContext, run_stage_by_name
from libs.basketball.teams import (
    FEATURE_DIM,
    H_BINS,
    S_BINS,
    cluster_tracks,
    torso_feature,
    torso_rect,
)
from libs.basketball.video import sample_frames

RATE = 30
BASE_FPS = 8.0

BoxFn = Callable[[float], Optional[Tuple[float, float, float, float]]]


# --- Synthetic clip + fake detect cache helpers --------------------------------


@dataclass
class ScriptedBox:
    """One rendered/detected rectangle: class id, fill color (RGB), motion."""

    class_id: int
    color_rgb: Tuple[int, int, int]
    box_at: BoxFn


def write_boxes_clip(
    path: Path,
    duration: float,
    bg_rgb: Tuple[int, int, int],
    objs: List[ScriptedBox],
    size: Tuple[int, int] = (320, 240),
    bg_at: Optional[Callable[[float], Tuple[int, int, int]]] = None,
) -> Path:
    """Encode solid background + filled moving rectangles into an MP4."""
    width, height = size
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=RATE)
    stream.width, stream.height = width, height
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 8_000_000
    for i in range(int(round(duration * RATE))):
        t = i / RATE
        img = np.empty((height, width, 3), dtype=np.uint8)
        img[:] = bg_at(t) if bg_at is not None else bg_rgb
        for obj in objs:
            box = obj.box_at(t)
            if box is None:
                continue
            x1, y1, x2, y2 = (int(round(v)) for v in box)
            img[max(y1, 0) : max(y2, 0), max(x1, 0) : max(x2, 0)] = obj.color_rgb
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        frame.pts = i
        frame.time_base = Fraction(1, RATE)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return path


def make_ctx(tmp_path: Path, clip_path: Path, settings: BasketballSettings) -> StageContext:
    clip_id = compute_clip_id(clip_path)
    return StageContext(
        stage="teams",
        clip_path=clip_path,
        clip_id=clip_id,
        settings=settings,
        cache=ClipCache(tmp_path / "work", clip_id),
    )


def build_detect_cache(ctx: StageContext, objs: List[ScriptedBox]) -> dict:
    """Fake detect-stage arrays.npz scripted from the same motion functions.

    frame_t comes from actually iterating ``sample_frames`` at base_fps — the
    exact code path/timestamps the real detect stage records.
    """
    boxes: List[Tuple[float, float, float, float]] = []
    scores: List[float] = []
    class_ids: List[int] = []
    frame_idx: List[int] = []
    frame_t: List[float] = []
    for k, (t, _frame) in enumerate(sample_frames(ctx.clip_path, ctx.settings.base_fps)):
        frame_t.append(t)
        for obj in objs:
            box = obj.box_at(t)
            if box is None:
                continue
            boxes.append(box)
            scores.append(0.9)
            class_ids.append(obj.class_id)
            frame_idx.append(k)
    arrays = {
        "boxes": np.asarray(boxes, dtype=np.float32).reshape(-1, 4),
        "scores": np.asarray(scores, dtype=np.float32),
        "class_ids": np.asarray(class_ids, dtype=np.int32),
        "frame_idx": np.asarray(frame_idx, dtype=np.int32),
        "frame_t": np.asarray(frame_t, dtype=np.float64),
    }
    ctx.cache.write_arrays("detect", arrays)
    ctx.cache.write_json("detect", {"clip_id": ctx.clip_id, "npz": "arrays.npz"})
    return arrays


def make_torso_frame(
    color_bgr: Tuple[int, int, int],
    box: Tuple[int, int, int, int] = (60, 40, 140, 190),
    noise: int = 10,
    seed: int = 7,
) -> np.ndarray:
    """A 200x200 BGR frame with one noisy solid-color 'player' rectangle."""
    rng = np.random.default_rng(seed)
    frame = np.full((200, 200, 3), 100, dtype=np.uint8)
    x1, y1, x2, y2 = box
    patch = np.full((y2 - y1, x2 - x1, 3), color_bgr, dtype=np.int16)
    patch += rng.integers(-noise, noise + 1, size=patch.shape, dtype=np.int16)
    frame[y1:y2, x1:x2] = patch.clip(0, 255).astype(np.uint8)
    return frame


def kit_feature(rng: np.random.Generator, hue_bin: Optional[int], sat_bin: int) -> np.ndarray:
    """Hand-built kit feature: mass in one hue bin (None = spread) + one sat bin."""
    feat = np.zeros(FEATURE_DIM)
    if hue_bin is None:
        feat[:H_BINS] = 1.0 / H_BINS  # desaturated kit: hue is noise-uniform
    else:
        feat[hue_bin] = 1.0
    feat[H_BINS + sat_bin] = 1.0
    feat[H_BINS + S_BINS + 2] = 1.0
    return feat + rng.uniform(0.0, 0.03, FEATURE_DIM)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# --- Torso-crop geometry --------------------------------------------------------


@pytest.mark.unit
def test_torso_rect_geometry():
    # 100-wide, 200-tall box; defaults keep the central 60% width, 20-60% height.
    assert torso_rect(np.array([100.0, 100.0, 200.0, 300.0])) == (120, 140, 180, 220)


@pytest.mark.unit
def test_torso_rect_full_box_when_fractions_cover_everything():
    assert torso_rect(np.array([0.0, 0.0, 10.0, 10.0]), top=0.0, bottom=1.0, inset_x=0.0) == (0, 0, 10, 10)


@pytest.mark.unit
def test_torso_rect_degenerate_box_is_empty():
    x1, y1, x2, y2 = torso_rect(np.array([50.0, 50.0, 50.0, 80.0]))
    assert x2 <= x1  # zero-width box -> empty torso


@pytest.mark.unit
def test_torso_feature_none_for_out_of_frame_box():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert torso_feature(frame, np.array([200.0, 200.0, 260.0, 300.0])) is None
    assert torso_feature(frame, np.array([10.0, 10.0, 10.0, 40.0])) is None


# --- HSV kit-color feature ------------------------------------------------------


@pytest.mark.unit
def test_torso_feature_invariant_to_small_box_jitter():
    frame = make_torso_frame(color_bgr=(30, 30, 200))  # red kit
    box = np.array([60.0, 40.0, 140.0, 190.0])
    base = torso_feature(frame, box)
    assert base is not None
    assert base.sum() == pytest.approx(3.0, abs=1e-6)  # three unit sub-histograms
    for jitter in ([3, -3, 2, 4], [-4, 2, -1, -5], [5, 5, 5, 5]):
        wiggled = torso_feature(frame, box + np.asarray(jitter, dtype=float))
        assert wiggled is not None
        assert cosine(base, wiggled) > 0.95


@pytest.mark.unit
def test_torso_feature_masks_dark_extremes():
    # Bottom half of the 'torso' is near-black shadow; the masked feature must
    # still look like the pure red kit, not a red/black mix.
    box = np.array([60.0, 40.0, 140.0, 190.0])
    red = make_torso_frame(color_bgr=(30, 30, 200), noise=5)
    shadowed = red.copy()
    shadowed[120:190, 60:140] = 5  # V < V_MASK_LO -> masked out
    feat_red = torso_feature(red, box)
    feat_shadowed = torso_feature(shadowed, box)
    assert feat_red is not None and feat_shadowed is not None
    assert cosine(feat_red, feat_shadowed) > 0.98


# --- Deterministic k=2 clustering ------------------------------------------------


def _two_kit_features(n_per_kit: int = 4, seed: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """(red features, white features): low-hue saturated vs hue-spread desaturated."""
    rng = np.random.default_rng(seed)
    reds = np.stack([kit_feature(rng, hue_bin=0, sat_bin=S_BINS - 1) for _ in range(n_per_kit)])
    whites = np.stack([kit_feature(rng, hue_bin=None, sat_bin=0) for _ in range(n_per_kit)])
    return reds, whites


@pytest.mark.unit
def test_cluster_numbering_deterministic_across_input_order():
    reds, whites = _two_kit_features()
    forward = cluster_tracks(np.concatenate([reds, whites]), min_silhouette=0.15)
    reversed_ = cluster_tracks(np.concatenate([whites, reds]), min_silhouette=0.15)
    # Red kits (lower mean hue) are cluster 0 no matter the input order.
    assert forward.labels[:4].tolist() == [0, 0, 0, 0]
    assert forward.labels[4:].tolist() == [1, 1, 1, 1]
    assert reversed_.labels[:4].tolist() == [1, 1, 1, 1]
    assert reversed_.labels[4:].tolist() == [0, 0, 0, 0]


@pytest.mark.unit
def test_cluster_confidence_high_for_separated_kits():
    reds, whites = _two_kit_features()
    result = cluster_tracks(np.concatenate([reds, whites]), min_silhouette=0.15)
    assert result.silhouette > 0.5
    assert (result.confidences > 0.6).all()


@pytest.mark.unit
def test_silhouette_gate_scales_down_confidence_for_similar_kits():
    rng = np.random.default_rng(11)
    base = kit_feature(np.random.default_rng(0), hue_bin=0, sat_bin=S_BINS - 1)
    # Two 'teams' whose center distance is far below the intra-team spread.
    group_a = base + rng.normal(0.0, 0.1, size=(4, FEATURE_DIM))
    group_b = base + 0.02 + rng.normal(0.0, 0.1, size=(4, FEATURE_DIM))
    gated = cluster_tracks(np.concatenate([group_a, group_b]), min_silhouette=0.15)
    assert gated.silhouette < 0.15
    assert set(gated.labels.tolist()) <= {0, 1}  # clusters still assigned
    assert gated.confidences.max() < 0.35  # ... but marked low-confidence
    ungated = cluster_tracks(np.concatenate([group_a, group_b]), min_silhouette=0.0)
    assert (gated.confidences <= ungated.confidences + 1e-12).all()


@pytest.mark.unit
def test_cluster_identical_features_degenerates_to_zero_confidence():
    features = np.tile(kit_feature(np.random.default_rng(0), hue_bin=0, sat_bin=7), (5, 1))
    result = cluster_tracks(features, min_silhouette=0.15)
    assert result.silhouette == 0.0
    assert (result.confidences == 0.0).all()


# --- run_stage: referee exclusion, cuts, tracker reset ---------------------------


def _static_box(x1: float, y1: float, x2: float, y2: float) -> BoxFn:
    return lambda t: (x1, y1, x2, y2)


@pytest.mark.unit
def test_run_stage_referee_only_yields_no_tracks(tmp_path):
    referee = ScriptedBox(class_id=5, color_rgb=(20, 20, 20), box_at=_static_box(140, 90, 180, 170))
    clip = write_boxes_clip(tmp_path / "ref.mp4", duration=2.0, bg_rgb=(90, 120, 80), objs=[referee])
    ctx = make_ctx(tmp_path, clip, BasketballSettings(base_fps=BASE_FPS))
    build_detect_cache(ctx, [referee])
    run_stage_by_name("teams", ctx)
    out = ctx.cache.read_json("teams")
    assert out["n_tracks"] == 0
    assert out["tracks"] == []
    assert out["cluster_stats"] == {"silhouette": None, "method": "hsv"}
    assert out["cuts"] == []


@pytest.mark.unit
def test_tracker_resets_at_camera_cut(tmp_path):
    cut_t = 1.5
    player = ScriptedBox(class_id=3, color_rgb=(230, 230, 230), box_at=_static_box(140, 90, 180, 170))

    def bg_at(t: float) -> Tuple[int, int, int]:
        return (140, 30, 30) if t < cut_t else (30, 60, 140)  # red court -> blue court

    clip = write_boxes_clip(tmp_path / "cut.mp4", duration=3.0, bg_rgb=(0, 0, 0), objs=[player], bg_at=bg_at)
    ctx = make_ctx(tmp_path, clip, BasketballSettings(base_fps=BASE_FPS))
    build_detect_cache(ctx, [player])
    run_stage_by_name("teams", ctx)
    out = ctx.cache.read_json("teams")

    assert len(out["cuts"]) == 1
    assert out["cuts"][0] == pytest.approx(cut_t, abs=0.2)
    # The same physical player continues across the cut, but no track bridges it.
    assert out["n_tracks"] >= 2
    for track in out["tracks"]:
        for cut in out["cuts"]:
            assert not (track["t_start"] < cut <= track["t_end"]), f"track {track['track_id']} bridges the cut"
    track_ids = [track["track_id"] for track in out["tracks"]]
    assert len(track_ids) == len(set(track_ids))  # globally unique despite tracker reset


# --- run_stage integration: two-team synthetic clip ------------------------------


@pytest.mark.integration
def test_run_stage_two_team_clip(tmp_path):
    duration, size = 5.0, (480, 270)
    red_rgb, white_rgb = (200, 30, 30), (235, 235, 235)

    def drifting(x0: float, y1: float, w: float = 26, h: float = 52) -> BoxFn:
        return lambda t: (x0 + 12.0 * t, y1, x0 + 12.0 * t + w, y1 + h)

    reds = [ScriptedBox(3, red_rgb, drifting(30 + 110 * i, 40)) for i in range(4)]
    whites = [ScriptedBox(3, white_rgb, drifting(30 + 110 * i, 170)) for i in range(4)]
    referee = ScriptedBox(5, (20, 20, 20), drifting(200, 105))

    def blink(t: float) -> Optional[Tuple[float, float, float, float]]:
        return (430.0, 20.0, 456.0, 72.0) if 0.79 <= t < 1.16 else None  # ~3 sampled frames

    tiny = ScriptedBox(3, red_rgb, blink)
    objs = reds + whites + [referee, tiny]

    clip = write_boxes_clip(tmp_path / "teams.mp4", duration, (90, 120, 80), objs, size=size)
    settings = BasketballSettings(base_fps=BASE_FPS)
    ctx = make_ctx(tmp_path, clip, settings)
    arrays = build_detect_cache(ctx, objs)
    run_stage_by_name("teams", ctx)
    out = ctx.cache.read_json("teams")

    # Exact output schema.
    assert set(out) == {"clip_id", "n_tracks", "tracks", "cluster_stats", "cuts"}
    assert out["clip_id"] == ctx.clip_id
    assert out["n_tracks"] == len(out["tracks"])
    assert out["cluster_stats"]["method"] == "hsv"
    for track in out["tracks"]:
        assert set(track) == {"track_id", "cluster", "cluster_confidence", "det_rows", "t_start", "t_end"}
        assert track["det_rows"] == sorted(set(track["det_rows"]))
        assert track["t_start"] <= track["t_end"]

    # Static background: no false cuts.
    assert out["cuts"] == []

    # Referee rows never enter any track.
    referee_rows = set(np.nonzero(arrays["class_ids"] == 5)[0].tolist())
    player_rows = set(np.nonzero(arrays["class_ids"] == 3)[0].tolist())
    all_track_rows = [row for track in out["tracks"] for row in track["det_rows"]]
    assert referee_rows.isdisjoint(all_track_rows)
    assert set(all_track_rows) <= player_rows
    assert len(all_track_rows) == len(set(all_track_rows))  # each detection in at most one track

    # The blinking player is a tiny track: cluster null, zero confidence.
    tiny_tracks = [t for t in out["tracks"] if t["cluster"] is None]
    assert len(tiny_tracks) == 1
    assert len(tiny_tracks[0]["det_rows"]) < settings.teams_min_track_dets
    assert tiny_tracks[0]["cluster_confidence"] == 0.0

    # Clustered tracks match the color groups, consistently and confidently.
    clustered = [t for t in out["tracks"] if t["cluster"] is not None]
    assert len(clustered) == 8

    def group_of(track: dict) -> str:
        y_centers = [(arrays["boxes"][row][1] + arrays["boxes"][row][3]) / 2.0 for row in track["det_rows"]]
        return "red" if float(np.mean(y_centers)) < 135 else "white"

    red_clusters = {t["cluster"] for t in clustered if group_of(t) == "red"}
    white_clusters = {t["cluster"] for t in clustered if group_of(t) == "white"}
    assert len([t for t in clustered if group_of(t) == "red"]) == 4
    assert len(red_clusters) == 1 and len(white_clusters) == 1
    assert red_clusters != white_clusters
    assert out["cluster_stats"]["silhouette"] >= settings.teams_min_silhouette
    assert all(t["cluster_confidence"] > 0.6 for t in clustered)

    # Debug npz: per-track aggregated features aligned with output tracks.
    npz = ctx.cache.read_arrays("teams")
    assert npz["track_ids"].tolist() == [t["track_id"] for t in out["tracks"]]
    assert npz["features"].shape == (out["n_tracks"], teams.FEATURE_DIM)
    clustered_ids = {t["track_id"] for t in clustered}
    for track_id, valid in zip(npz["track_ids"].tolist(), npz["feature_valid"].tolist()):
        if track_id in clustered_ids:
            assert valid


@pytest.mark.unit
def test_run_stage_is_warm_skips_and_force_reruns(tmp_path):
    player = ScriptedBox(class_id=3, color_rgb=(200, 30, 30), box_at=_static_box(140, 90, 180, 170))
    clip = write_boxes_clip(tmp_path / "warm.mp4", duration=1.0, bg_rgb=(90, 120, 80), objs=[player])
    ctx = make_ctx(tmp_path, clip, BasketballSettings(base_fps=BASE_FPS))
    build_detect_cache(ctx, [player])
    run_stage_by_name("teams", ctx)
    marker = ctx.cache.path("teams", "output.json")
    stamp = marker.stat().st_mtime_ns
    run_stage_by_name("teams", ctx)  # warm -> no rewrite
    assert marker.stat().st_mtime_ns == stamp
    ctx.force = True
    run_stage_by_name("teams", ctx)
    assert ctx.cache.read_json("teams")["clip_id"] == ctx.clip_id


@pytest.mark.unit
def test_run_stage_raises_without_detect_cache(tmp_path):
    clip = write_boxes_clip(tmp_path / "cold.mp4", duration=0.5, bg_rgb=(90, 120, 80), objs=[])
    ctx = make_ctx(tmp_path, clip, BasketballSettings(base_fps=BASE_FPS))
    with pytest.raises(FileNotFoundError):
        run_stage_by_name("teams", ctx)
