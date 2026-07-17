"""Tests for libs/basketball/jersey.py (jersey stage, Epic 3 story 2).

Unit tests exercise the pure helpers (association geometry, legibility gate,
digit normalization, tracklet vote, roster mapping) and the stage wiring with
OCR faked out. The integration tests at the bottom render synthetic clips
with cv2.putText jersey numbers and run the real RapidOCR recognizer.

Run with the standalone basketball venv:

    .venv-basketball/bin/python -m pytest tests/basketball/test_jersey.py -v
"""

import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import av
import cv2
import numpy as np
import pytest

from libs.basketball import jersey
from libs.basketball.cache import ClipCache, compute_clip_id
from libs.basketball.config import BasketballSettings
from libs.basketball.jersey import (
    apply_roster,
    associate_number,
    is_legible,
    normalize_jersey_text,
    sharpness,
    vote_jersey,
)
from libs.basketball.stages import StageContext, run_stage_by_name
from libs.basketball.video import sample_frames

FONT = cv2.FONT_HERSHEY_SIMPLEX
WIDTH, HEIGHT = 320, 240
RATE = 30


# --- Shared helpers -----------------------------------------------------------


def make_digit_crop(text="23", h=24, jersey_bgr=(160, 60, 40), blur=0):
    """Synthetic number crop: white digits centered on a jersey-colored patch."""
    scale = h / 24.0
    w = int(h * (0.9 + 0.7 * len(text)))
    img = np.full((h, w, 3), jersey_bgr, dtype=np.uint8)
    font_scale, thickness = 0.8 * scale, max(1, int(2 * scale))
    (tw, th), _base = cv2.getTextSize(text, FONT, font_scale, thickness)
    cv2.putText(img, text, ((w - tw) // 2, (h + th) // 2), FONT, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    if blur:
        img = cv2.GaussianBlur(img, (blur, blur), 0)
    return img


def make_ctx(clip: Path, workdir: Path, **settings_overrides) -> StageContext:
    settings = BasketballSettings(workdir=str(workdir), **settings_overrides)
    clip_id = compute_clip_id(clip)
    return StageContext(
        stage="jersey",
        clip_path=clip,
        clip_id=clip_id,
        settings=settings,
        cache=ClipCache(workdir, clip_id),
    )


def write_detect_arrays(cache: ClipCache, rows, frame_ts):
    """rows: list of (frame_idx, class_id, xyxy box) -> detect arrays.npz."""
    n = len(rows)
    cache.write_arrays(
        "detect",
        {
            "boxes": np.array([r[2] for r in rows], dtype=np.float32).reshape(n, 4),
            "scores": np.full((n,), 0.9, dtype=np.float32),
            "class_ids": np.array([r[1] for r in rows], dtype=np.int32),
            "frame_idx": np.array([r[0] for r in rows], dtype=np.int32),
            "frame_t": np.asarray(frame_ts, dtype=np.float64),
        },
    )


def write_teams_output(cache: ClipCache, clip_id, tracks, frame_ts):
    full_tracks = [
        {
            "track_id": t["track_id"],
            "cluster": t.get("cluster", 0),
            "cluster_confidence": t.get("cluster_confidence", 0.9),
            "det_rows": t["det_rows"],
            "t_start": frame_ts[0],
            "t_end": frame_ts[-1],
        }
        for t in tracks
    ]
    cache.write_json(
        "teams",
        {
            "clip_id": clip_id,
            "n_tracks": len(full_tracks),
            "tracks": full_tracks,
            "cluster_stats": {},
            "cuts": [],
        },
    )


# --- Crop association ----------------------------------------------------------


@pytest.mark.unit
class TestAssociation:
    def test_center_containment(self):
        number = [10, 10, 20, 20]  # center (15, 15)
        candidates = [[0, 0, 30, 30], [16, 0, 40, 40]]  # only the first contains the center
        assert associate_number(number, candidates) == 0

    def test_tie_breaks_to_smallest_containing_box(self):
        number = [10, 10, 20, 20]
        candidates = [[0, 0, 100, 100], [5, 5, 25, 25], [0, 0, 60, 60]]
        assert associate_number(number, candidates) == 1

    def test_no_containing_box_returns_none(self):
        assert associate_number([10, 10, 20, 20], [[30, 30, 50, 50]]) is None
        assert associate_number([10, 10, 20, 20], []) is None

    def test_boundary_is_inclusive(self):
        number = [10, 10, 20, 20]  # center (15, 15)
        assert associate_number(number, [[15, 0, 40, 40]]) == 0  # cx exactly on x1

    def test_overlap_without_center_containment_is_unassociated(self):
        number = [10, 10, 30, 30]  # center (20, 20)
        assert associate_number(number, [[21, 0, 60, 60]]) is None  # boxes overlap, center outside


# --- Legibility gate -------------------------------------------------------------


@pytest.mark.unit
class TestLegibilityGate:
    MIN_PX, MIN_SHARP = 12, 40.0  # config defaults

    def test_sharp_crop_passes(self):
        assert is_legible(make_digit_crop("23", h=24), self.MIN_PX, self.MIN_SHARP)

    def test_blurred_crop_rejected(self):
        assert not is_legible(make_digit_crop("23", h=24, blur=15), self.MIN_PX, self.MIN_SHARP)

    def test_sharpness_monotonic_under_blur(self):
        sharp = sharpness(make_digit_crop("23", h=24))
        blurred = sharpness(make_digit_crop("23", h=24, blur=15))
        assert sharp > self.MIN_SHARP > blurred

    def test_tiny_crop_rejected_even_when_sharp(self):
        assert not is_legible(make_digit_crop("23", h=8), self.MIN_PX, self.MIN_SHARP)

    def test_degenerate_crops_rejected(self):
        assert not is_legible(np.zeros((0, 0, 3), dtype=np.uint8), self.MIN_PX, self.MIN_SHARP)
        assert not is_legible(np.zeros((30, 1, 3), dtype=np.uint8), self.MIN_PX, self.MIN_SHARP)


# --- Digit normalization ----------------------------------------------------------


@pytest.mark.unit
class TestNormalization:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (" 23 ", "23"),
            ("4", "4"),
            ("44", "44"),  # stays double-digit, never merged with "4"
            ("O4", "4"),  # O -> 0, then "04" canonicalizes to "4"
            ("S", "5"),
            ("B", "8"),
            ("I", "1"),
            ("L", "1"),
            ("l2", "12"),
            ("2 3", "23"),  # internal whitespace removed
            ("07", "7"),
        ],
    )
    def test_valid_reads(self, raw, expected):
        assert normalize_jersey_text(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "123", "4.5", "AB4", "の", "²", "-4", None])
    def test_garbage_rejected(self, raw):
        assert normalize_jersey_text(raw) is None


# --- Tracklet vote -----------------------------------------------------------------


@pytest.mark.unit
class TestVote:
    def test_three_consistent_beat_one_outlier(self):
        number, conf = vote_jersey(Counter({"4": 3, "7": 1}), min_reads=3, vote_margin=2)
        assert number == "4"
        assert 0.0 < conf <= 1.0

    def test_two_two_split_is_null(self):
        assert vote_jersey(Counter({"4": 2, "7": 2}), 3, 2) == (None, 0.0)

    def test_single_vs_double_digit_never_merged(self):
        assert vote_jersey(Counter({"4": 2, "44": 2}), 3, 2) == (None, 0.0)
        number, _conf = vote_jersey(Counter({"44": 4, "4": 1}), 3, 2)
        assert number == "44"

    def test_margin_rule(self):
        assert vote_jersey(Counter({"4": 3, "44": 2}), 3, 2) == (None, 0.0)  # margin 1 < 2
        number, conf = vote_jersey(Counter({"4": 4, "44": 2}), 3, 2)  # margin 2
        assert number == "4" and conf > 0.0

    def test_min_reads_rule(self):
        assert vote_jersey(Counter({"4": 2}), 3, 2) == (None, 0.0)  # margin fine, too few reads
        number, _conf = vote_jersey(Counter({"4": 3}), 3, 2)
        assert number == "4"

    def test_empty_votes(self):
        assert vote_jersey(Counter(), 3, 2) == (None, 0.0)

    def test_confidence_grows_with_read_count(self):
        _n3, conf3 = vote_jersey(Counter({"23": 3}), 3, 2)
        _n6, conf6 = vote_jersey(Counter({"23": 6}), 3, 2)
        assert 0.0 < conf3 < conf6 <= 1.0

    def test_confidence_shrinks_with_dissent(self):
        _u, unanimous = vote_jersey(Counter({"23": 5}), 3, 2)
        _d, dissent = vote_jersey(Counter({"23": 5, "28": 2}), 3, 2)
        assert dissent < unanimous


# --- Roster helper -----------------------------------------------------------------


@pytest.mark.unit
class TestRoster:
    TRACKS = [
        {"track_id": 1, "jersey": "23", "confidence": 0.8, "n_reads": 5, "votes": {"23": 5}},
        {"track_id": 2, "jersey": None, "confidence": 0.0, "n_reads": 1, "votes": {"7": 1}},
        {"track_id": 3, "jersey": "7", "confidence": 0.5, "n_reads": 3, "votes": {"7": 3}},
    ]

    def test_names_attached_by_jersey(self):
        out = apply_roster(self.TRACKS, {"23": "M. Jordan", "07": "K. Toney"})
        assert out[0]["player_name"] == "M. Jordan"
        assert out[1]["player_name"] is None  # null jersey -> no name
        assert out[2]["player_name"] == "K. Toney"  # roster "07" matches jersey "7"

    def test_int_roster_keys_supported(self):
        out = apply_roster(self.TRACKS, {23: "M. Jordan"})
        assert out[0]["player_name"] == "M. Jordan"

    def test_unmapped_jersey_gets_none(self):
        out = apply_roster(self.TRACKS, {"99": "Nobody"})
        assert all(t["player_name"] is None for t in out)

    def test_pure_no_mutation(self):
        before = [dict(t) for t in self.TRACKS]
        apply_roster(self.TRACKS, {"23": "M. Jordan"})
        assert self.TRACKS == before
        assert all("player_name" not in t for t in self.TRACKS)

    def test_empty_roster(self):
        out = apply_roster(self.TRACKS, {})
        assert all(t["player_name"] is None for t in out)


# --- run_stage wiring (OCR faked out) -----------------------------------------------


PLAYER, NUMBER = jersey.PLAYER_CLASS_ID, jersey.NUMBER_CLASS_ID


@pytest.mark.unit
class TestRunStageWiring:
    def test_missing_detect_raises(self, cfr_clip, tmp_path):
        ctx = make_ctx(cfr_clip, tmp_path / "work")
        with pytest.raises(FileNotFoundError):
            run_stage_by_name("jersey", ctx)
        assert not ctx.cache.is_warm("jersey")

    def test_warm_skip_and_force(self, cfr_clip, tmp_path):
        ctx = make_ctx(cfr_clip, tmp_path / "work")
        ctx.cache.write_json("jersey", {"clip_id": ctx.clip_id, "tracks": [], "unassociated_numbers": 0})
        run_stage_by_name("jersey", ctx)  # warm -> no-op (would raise on missing detect otherwise)
        ctx.force = True
        with pytest.raises(FileNotFoundError):
            run_stage_by_name("jersey", ctx)

    def test_tracks_without_number_dets_emit_null(self, cfr_clip, tmp_path):
        ctx = make_ctx(cfr_clip, tmp_path / "work")
        rows = [(0, PLAYER, [10, 10, 110, 210]), (1, PLAYER, [10, 10, 110, 210])]
        write_detect_arrays(ctx.cache, rows, [0.0, 0.5])
        write_teams_output(ctx.cache, ctx.clip_id, [{"track_id": 7, "det_rows": [0, 1]}], [0.0, 0.5])
        run_stage_by_name("jersey", ctx)
        out = ctx.cache.read_json("jersey")
        assert out == {
            "clip_id": ctx.clip_id,
            "tracks": [{"track_id": 7, "jersey": None, "confidence": 0.0, "n_reads": 0, "votes": {}}],
            "unassociated_numbers": 0,
        }

    def test_missing_teams_falls_back_to_pseudo_tracks(self, cfr_clip, tmp_path):
        # No teams output; the lone number det sits inside no player box.
        ctx = make_ctx(cfr_clip, tmp_path / "work")
        rows = [
            (0, PLAYER, [10, 10, 110, 210]),
            (0, NUMBER, [150, 60, 170, 90]),  # center (160, 75): outside the player box
        ]
        write_detect_arrays(ctx.cache, rows, [0.0])
        run_stage_by_name("jersey", ctx)  # must not raise despite the missing teams stage
        out = ctx.cache.read_json("jersey")
        assert out["tracks"] == []  # pseudo-tracks without an associated number are dropped
        assert out["unassociated_numbers"] == 1

    def test_association_votes_and_margins_end_to_end(self, cfr_clip, tmp_path, monkeypatch):
        """Fake OCR keyed on crop width: track A reads '4' 3x (accepted),
        track B reads '23' 2x (below min_reads -> null)."""
        frame_ts = [t for t, _f in sample_frames(cfr_clip, 8.0)]
        assert len(frame_ts) >= 3
        rows = []
        for k in range(3):
            rows.append((k, PLAYER, [10, 10, 110, 210]))  # track A player
            rows.append((k, NUMBER, [40, 60, 60, 90]))  # 20 px wide -> "4"
        for k in range(2):
            rows.append((k, PLAYER, [200, 10, 300, 210]))  # track B player
            rows.append((k, NUMBER, [220, 60, 260, 90]))  # 40 px wide -> "23"
        rows.append((0, NUMBER, [150, 60, 170, 90]))  # center in no player box

        ctx = make_ctx(cfr_clip, tmp_path / "work", base_fps=8.0)
        write_detect_arrays(ctx.cache, rows, frame_ts)
        a_rows = [i for i, r in enumerate(rows) if r[1] == PLAYER and r[2][0] == 10]
        b_rows = [i for i, r in enumerate(rows) if r[1] == PLAYER and r[2][0] == 200]
        write_teams_output(
            ctx.cache,
            ctx.clip_id,
            [{"track_id": 1, "det_rows": a_rows}, {"track_id": 2, "det_rows": b_rows}],
            frame_ts,
        )

        monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", SimpleNamespace(RapidOCR=lambda: None))
        monkeypatch.setattr(jersey, "is_legible", lambda crop, min_px, min_sharp: True)
        monkeypatch.setattr(jersey, "read_number", lambda crop, ocr: ("4", 0.9) if crop.shape[1] == 20 else ("23", 0.9))

        run_stage_by_name("jersey", ctx)
        out = ctx.cache.read_json("jersey")
        by_id = {t["track_id"]: t for t in out["tracks"]}
        assert by_id[1] == {"track_id": 1, "jersey": "4", "confidence": 0.5, "n_reads": 3, "votes": {"4": 3}}
        assert by_id[2] == {"track_id": 2, "jersey": None, "confidence": 0.0, "n_reads": 2, "votes": {"23": 2}}
        assert out["unassociated_numbers"] == 1

    def test_misaligned_base_fps_raises(self, cfr_clip, tmp_path, monkeypatch):
        # detect cache indexed at 8 fps, but the stage now runs at 4 fps -> PTS mismatch.
        frame_ts = [t for t, _f in sample_frames(cfr_clip, 8.0)]
        rows = [(1, PLAYER, [10, 10, 110, 210]), (1, NUMBER, [40, 60, 60, 90])]
        ctx = make_ctx(cfr_clip, tmp_path / "work", base_fps=4.0)
        write_detect_arrays(ctx.cache, rows, frame_ts)
        write_teams_output(ctx.cache, ctx.clip_id, [{"track_id": 1, "det_rows": [0]}], frame_ts)
        monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", SimpleNamespace(RapidOCR=lambda: None))
        with pytest.raises(RuntimeError, match="misaligned"):
            run_stage_by_name("jersey", ctx)
        assert not ctx.cache.is_warm("jersey")


# --- Integration: real RapidOCR on synthetic putText clips ---------------------------


PLAYER_A_RECT = (20, 40, 100, 220)  # x1, y1, x2, y2
PLAYER_B_RECT = (200, 40, 290, 220)


def draw_number(img, text, center, font_scale=0.9, thickness=2):
    """putText a number; returns its padded bounding box (xyxy floats)."""
    (tw, th), baseline = cv2.getTextSize(text, FONT, font_scale, thickness)
    org = (int(center[0] - tw / 2), int(center[1] + th / 2))
    cv2.putText(img, text, org, FONT, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    pad = 4
    return [org[0] - pad, org[1] - th - pad, org[0] + tw + pad, org[1] + baseline + pad]


def render_game_frame():
    """One 320x240 broadcast-ish frame; returns (image, number boxes dict)."""
    img = np.full((HEIGHT, WIDTH, 3), (35, 45, 40), dtype=np.uint8)
    cv2.rectangle(img, PLAYER_A_RECT[:2], PLAYER_A_RECT[2:], (160, 60, 40), -1)  # blue-ish jersey
    cv2.rectangle(img, PLAYER_B_RECT[:2], PLAYER_B_RECT[2:], (40, 60, 160), -1)  # red-ish jersey
    boxes = {
        "num_a": draw_number(img, "4", (60, 110)),
        "num_b": draw_number(img, "23", (245, 110)),
        "num_stray": draw_number(img, "7", (150, 200)),  # inside neither player box
    }
    return img, boxes


def write_game_clip(path: Path, n_frames=36, rate=RATE):
    """Encode n_frames identical rendered frames; returns the number boxes."""
    img, boxes = render_game_frame()
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=rate)
    stream.width, stream.height = WIDTH, HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 8_000_000  # keep the digits crisp through encoding
    for i in range(n_frames):
        frame = av.VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = i
        frame.time_base = Fraction(1, rate)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return boxes


def build_game_fixture(tmp_path, **settings_overrides):
    """Clip + fake detect npz (players/numbers per sampled frame) -> (ctx, meta)."""
    clip = tmp_path / "game.mp4"
    boxes = write_game_clip(clip)
    ctx = make_ctx(clip, tmp_path / "work", base_fps=4.0, **settings_overrides)
    frame_ts = [t for t, _f in sample_frames(clip, ctx.settings.base_fps)]
    assert len(frame_ts) >= 3

    rows, a_rows, b_rows = [], [], []
    for k in range(len(frame_ts)):
        a_rows.append(len(rows))
        rows.append((k, PLAYER, list(PLAYER_A_RECT)))
        b_rows.append(len(rows))
        rows.append((k, PLAYER, list(PLAYER_B_RECT)))
        rows.append((k, NUMBER, boxes["num_a"]))
        rows.append((k, NUMBER, boxes["num_b"]))
        rows.append((k, NUMBER, boxes["num_stray"]))
    write_detect_arrays(ctx.cache, rows, frame_ts)
    return ctx, {"frame_ts": frame_ts, "a_rows": a_rows, "b_rows": b_rows}


@pytest.mark.integration
class TestRealOcrIntegration:
    def test_stage_votes_correct_numbers(self, tmp_path):
        ctx, meta = build_game_fixture(tmp_path)
        write_teams_output(
            ctx.cache,
            ctx.clip_id,
            [{"track_id": 1, "det_rows": meta["a_rows"]}, {"track_id": 2, "det_rows": meta["b_rows"]}],
            meta["frame_ts"],
        )
        run_stage_by_name("jersey", ctx)

        assert ctx.cache.is_warm("jersey")
        out = ctx.cache.read_json("jersey")
        assert set(out) == {"clip_id", "tracks", "unassociated_numbers"}
        assert out["clip_id"] == ctx.clip_id
        assert out["unassociated_numbers"] == len(meta["frame_ts"])  # one stray number per frame

        by_id = {t["track_id"]: t for t in out["tracks"]}
        assert set(by_id) == {1, 2}
        assert by_id[1]["jersey"] == "4"
        assert by_id[2]["jersey"] == "23"
        for track in out["tracks"]:
            assert set(track) == {"track_id", "jersey", "confidence", "n_reads", "votes"}
            assert track["n_reads"] >= ctx.settings.jersey_min_reads
            assert 0.0 < track["confidence"] <= 1.0
            # the voted number must dominate the ballot
            assert track["votes"][track["jersey"]] == max(track["votes"].values())

    def test_pseudo_track_fallback_reads_numbers(self, tmp_path):
        # No teams output: every player det row is its own single-frame track.
        # Lenient thresholds let single reads through so the OCR path is proven.
        ctx, meta = build_game_fixture(tmp_path, jersey_min_reads=1, jersey_vote_margin=1)
        run_stage_by_name("jersey", ctx)

        out = ctx.cache.read_json("jersey")
        assert out["unassociated_numbers"] == len(meta["frame_ts"])
        # pseudo track_ids are detect npz row indices of the player detections
        assert {t["track_id"] for t in out["tracks"]} <= set(meta["a_rows"]) | set(meta["b_rows"])
        read_a = [t["jersey"] for t in out["tracks"] if t["track_id"] in meta["a_rows"] and t["jersey"]]
        read_b = [t["jersey"] for t in out["tracks"] if t["track_id"] in meta["b_rows"] and t["jersey"]]
        assert read_a and set(read_a) == {"4"}
        assert read_b and set(read_b) == {"23"}

    def test_default_thresholds_keep_single_frame_tracks_null(self, tmp_path):
        # Same fallback with production thresholds: one read can never clear
        # min_reads=3, so every pseudo-track must stay null (never confidently wrong).
        ctx, _meta = build_game_fixture(tmp_path)
        run_stage_by_name("jersey", ctx)
        out = ctx.cache.read_json("jersey")
        assert out["tracks"]  # associations happened...
        assert all(t["jersey"] is None and t["confidence"] == 0.0 for t in out["tracks"])
