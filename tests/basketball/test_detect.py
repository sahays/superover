"""Tests for libs/basketball/detect.py (detect stage, Epic 2 story 2).

Unit tests need no ONNX model: the onnxruntime session is faked. The
integration tests at the bottom run the real COCO smoke-test export and are
skipped when libs/basketball/models/*.onnx is absent (see models/README.md).
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from libs.basketball import detect
from libs.basketball.cache import ClipCache, compute_clip_id
from libs.basketball.config import BasketballSettings
from libs.basketball.detect import (
    CANONICAL_CLASSES,
    YoloOnnxDetector,
    letterbox,
    letterbox_boxes,
    nms,
    unletterbox_boxes,
)
from libs.basketball.stages import StageContext, run_stage_by_name

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "libs" / "basketball" / "models"
COCO_ONNX_640 = MODELS_DIR / "yolo11n-coco-640.onnx"

# Fake-session geometry: 320x240 source (conftest clips) into a 64x64 input
# gives scale 0.2, pad_x 0, pad_y 8 — round numbers for exact assertions.
INPUT = 64
SMOKE_CLASS_MAP = {"person": "player", "sports ball": "ball"}
COCO_NAMES_META = "{0: 'person', 1: 'sports ball'}"


# --- Fake onnxruntime ---------------------------------------------------------


class FakeSessionOptions:
    def __init__(self):
        self.intra_op_num_threads = 0


def fake_ort(output, names_meta=None, end2end=None, input_shape=(1, 3, INPUT, INPUT)):
    """A namespace that stands in for the onnxruntime module in detect.py.

    ``output`` is the canned tensor `session.run` returns (or a callable of
    the feed dict producing one).
    """

    class FakeSession:
        def __init__(self, path, sess_options=None, providers=None):
            self.path = path
            self.sess_options = sess_options
            self.providers = providers

        def get_inputs(self):
            return [SimpleNamespace(name="images", shape=list(input_shape))]

        def get_modelmeta(self):
            meta = {}
            if names_meta is not None:
                meta["names"] = names_meta
            if end2end is not None:
                meta["end2end"] = end2end
            return SimpleNamespace(custom_metadata_map=meta)

        def run(self, _output_names, feeds):
            result = output(feeds) if callable(output) else output
            return [result]

    return SimpleNamespace(InferenceSession=FakeSession, SessionOptions=FakeSessionOptions)


def raw_grid(dets, nc, n_junk=10):
    """Build a raw-grid output (1, 4+nc, N): rows of cxcywh + per-class scores."""
    rows = [[cx, cy, w, h, *scores] for cx, cy, w, h, scores in dets]
    rows += [[5.0 + i, 5.0, 4.0, 4.0, *([0.01] * nc)] for i in range(n_junk)]
    return np.array(rows, dtype=np.float32).T[None]


def make_detector(
    monkeypatch,
    output,
    tmp_path,
    *,
    names_meta=COCO_NAMES_META,
    end2end=None,
    input_shape=(1, 3, INPUT, INPUT),
    **kwargs,
):
    monkeypatch.setattr(detect, "ort", fake_ort(output, names_meta, end2end, input_shape))
    model = tmp_path / "fake.onnx"
    model.write_bytes(b"not a real model")
    kwargs.setdefault("class_map", SMOKE_CLASS_MAP)
    return YoloOnnxDetector(model, **kwargs)


# --- Letterbox ------------------------------------------------------------------


@pytest.mark.unit
class TestLetterbox:
    def test_landscape_geometry_and_padding(self):
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        canvas, scale, (pad_x, pad_y) = letterbox(img, (INPUT, INPUT))
        assert canvas.shape == (INPUT, INPUT, 3)
        assert scale == pytest.approx(0.2)
        assert (pad_x, pad_y) == (0.0, 8.0)
        assert (canvas[0] == detect.PAD_COLOR).all()  # top pad row is gray
        assert (canvas[INPUT // 2] == 0).any() or (canvas[INPUT // 2] == 0).all()  # image row

    def test_portrait_pads_horizontally(self):
        img = np.zeros((320, 240, 3), dtype=np.uint8)
        _, scale, (pad_x, pad_y) = letterbox(img, (INPUT, INPUT))
        assert scale == pytest.approx(0.2)
        assert (pad_x, pad_y) == (8.0, 0.0)

    def test_box_round_trip_source_to_canvas_and_back(self):
        rng = np.random.default_rng(7)
        x1 = rng.uniform(0, 200, size=(20, 1))
        y1 = rng.uniform(0, 150, size=(20, 1))
        boxes = np.hstack([x1, y1, x1 + rng.uniform(1, 100, (20, 1)), y1 + rng.uniform(1, 80, (20, 1))])
        _, scale, pads = letterbox(np.zeros((240, 320, 3), dtype=np.uint8), (INPUT, INPUT))
        round_tripped = unletterbox_boxes(letterbox_boxes(boxes, scale, pads), scale, pads, (240, 320))
        np.testing.assert_allclose(round_tripped, boxes, atol=1e-4)

    def test_unletterbox_clips_to_source_bounds(self):
        _, scale, pads = letterbox(np.zeros((240, 320, 3), dtype=np.uint8), (INPUT, INPUT))
        outside = np.array([[-10.0, 0.0, 500.0, 500.0]])  # canvas coords past every edge
        mapped = unletterbox_boxes(outside, scale, pads, (240, 320))
        assert mapped[0, 0] >= 0 and mapped[0, 1] >= 0
        assert mapped[0, 2] <= 320 and mapped[0, 3] <= 240


# --- NMS ------------------------------------------------------------------------


@pytest.mark.unit
class TestNms:
    def test_suppresses_overlap_keeps_highest_score(self):
        boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
        scores = np.array([0.6, 0.9, 0.5], dtype=np.float32)
        keep = nms(boxes, scores, iou_threshold=0.5)
        assert sorted(keep.tolist()) == [1, 2]  # highest-scoring overlap wins

    def test_disjoint_boxes_all_kept(self):
        boxes = np.array([[0, 0, 10, 10], [20, 20, 30, 30], [40, 40, 50, 50]], dtype=np.float32)
        keep = nms(boxes, np.array([0.9, 0.8, 0.7], dtype=np.float32))
        assert sorted(keep.tolist()) == [0, 1, 2]

    def test_empty_input(self):
        keep = nms(np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32))
        assert keep.shape == (0,)

    def test_class_aware_keeps_same_spot_different_class(self):
        boxes = np.array([[0, 0, 10, 10], [0, 0, 10, 10]], dtype=np.float32)
        scores = np.array([0.9, 0.8], dtype=np.float32)
        same_class = detect._class_aware_nms(boxes, scores, np.array([0, 0]), 0.5)
        different_class = detect._class_aware_nms(boxes, scores, np.array([0, 1]), 0.5)
        assert len(same_class) == 1
        assert len(different_class) == 2


# --- Decoding, mapping, thresholds (fake session) -------------------------------


@pytest.mark.unit
class TestDetectorDecoding:
    # One strong person, one strong ball, a duplicate person (NMS food), junk
    # anchors below threshold. cxcywh in 64x64 letterbox space.
    DETS = [
        (32.0, 32.0, 20.0, 24.0, (0.90, 0.02)),  # person -> player
        (33.0, 33.0, 20.0, 24.0, (0.60, 0.02)),  # duplicate person, suppressed
        (10.0, 12.0, 6.0, 6.0, (0.02, 0.80)),  # sports ball -> ball
    ]

    def _assert_smoke_detections(self, dets):
        assert dets.boxes.shape == (2, 4)
        by_class = {int(c): dets.boxes[i] for i, c in enumerate(dets.class_ids)}
        assert set(by_class) == {0, 3}  # ball=0, player=3
        np.testing.assert_allclose(by_class[3], [110.0, 60.0, 210.0, 180.0], atol=1e-3)
        np.testing.assert_allclose(by_class[0], [35.0, 5.0, 65.0, 35.0], atol=1e-3)

    def test_raw_grid_decode_nms_and_coord_mapping(self, monkeypatch, tmp_path):
        detector = make_detector(monkeypatch, raw_grid(self.DETS, nc=2), tmp_path)
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        self._assert_smoke_detections(dets)
        assert dets.boxes.dtype == np.float32
        assert dets.scores.dtype == np.float32
        assert dets.class_ids.dtype == np.int32

    def test_raw_grid_transposed_orientation(self, monkeypatch, tmp_path):
        # (1, N, 6) with nc=2 is shape-identical to an end-to-end output; the
        # explicit end2end=False metadata (as ultralytics writes) must win.
        transposed = raw_grid(self.DETS, nc=2).transpose(0, 2, 1)  # (1, N, 4+nc)
        detector = make_detector(monkeypatch, transposed, tmp_path, end2end="False")
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        self._assert_smoke_detections(dets)

    def test_raw_grid_without_names_metadata_uses_class_map_order(self, monkeypatch, tmp_path):
        detector = make_detector(monkeypatch, raw_grid(self.DETS, nc=2), tmp_path, names_meta=None)
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        self._assert_smoke_detections(dets)  # id 0 -> "person" (first map key) -> player

    def test_end_to_end_decode_thresholds_only_no_nms(self, monkeypatch, tmp_path):
        rows = np.array(
            [
                [22.0, 20.0, 42.0, 44.0, 0.90, 0.0],  # person
                [23.0, 21.0, 43.0, 45.0, 0.80, 0.0],  # overlapping person: e2e output is trusted, kept
                [10.0, 10.0, 20.0, 20.0, 0.10, 1.0],  # below threshold, dropped
            ],
            dtype=np.float32,
        )[None]
        detector = make_detector(monkeypatch, rows, tmp_path, end2end="True")
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        assert dets.boxes.shape == (2, 4)
        assert (dets.class_ids == 3).all()  # both persons -> player
        np.testing.assert_allclose(dets.boxes[0], [110.0, 60.0, 210.0, 180.0], atol=1e-3)

    def test_end_to_end_shape_detected_without_metadata(self, monkeypatch, tmp_path):
        rows = np.array([[22.0, 20.0, 42.0, 44.0, 0.90, 1.0]], dtype=np.float32)[None]
        detector = make_detector(monkeypatch, rows, tmp_path)  # no end2end meta; (1, N, 6) shape decides
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        assert dets.boxes.shape == (1, 4)
        assert dets.class_ids[0] == 0  # sports ball -> ball

    def test_global_confidence_threshold_filters(self, monkeypatch, tmp_path):
        weak = [(32.0, 32.0, 20.0, 24.0, (0.20, 0.02))]
        detector = make_detector(monkeypatch, raw_grid(weak, nc=2), tmp_path, conf=0.25)
        assert detector.detect(np.zeros((240, 320, 3), dtype=np.uint8)).boxes.shape == (0, 4)
        detector = make_detector(monkeypatch, raw_grid(weak, nc=2), tmp_path, conf=0.15)
        assert detector.detect(np.zeros((240, 320, 3), dtype=np.uint8)).boxes.shape == (1, 4)

    def test_per_class_threshold_overrides_global(self, monkeypatch, tmp_path):
        weak_pair = [
            (32.0, 32.0, 20.0, 24.0, (0.15, 0.02)),  # person @ 0.15
            (10.0, 12.0, 6.0, 6.0, (0.02, 0.15)),  # ball   @ 0.15
        ]
        detector = make_detector(
            monkeypatch, raw_grid(weak_pair, nc=2), tmp_path, conf=0.25, per_class_conf={"ball": 0.1}
        )
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        assert dets.class_ids.tolist() == [0]  # ball kept by its looser threshold, person dropped

    def test_unknown_class_names_pass_through_with_id_after_canonical(self, monkeypatch, tmp_path):
        names = "{0: 'person', 1: 'sports ball', 2: 'hoopla'}"
        dets_in = [(32.0, 32.0, 20.0, 24.0, (0.02, 0.02, 0.9))]
        detector = make_detector(monkeypatch, raw_grid(dets_in, nc=3), tmp_path, names_meta=names)
        assert detector.class_names[:6] == list(CANONICAL_CLASSES)
        assert detector.class_names[6] == "hoopla"
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        assert dets.class_ids.tolist() == [6]

    def test_static_input_shape_overrides_requested_size(self, monkeypatch, tmp_path):
        detector = make_detector(monkeypatch, raw_grid([], nc=2), tmp_path, input_size=960)
        assert detector.input_size == (INPUT, INPUT)

    def test_dynamic_input_shape_uses_requested_size(self, monkeypatch, tmp_path):
        detector = make_detector(
            monkeypatch,
            raw_grid([], nc=2),
            tmp_path,
            input_shape=(1, 3, "height", "width"),
            input_size=32,
        )
        assert detector.input_size == (32, 32)

    def test_no_detections_returns_empty_typed_arrays(self, monkeypatch, tmp_path):
        detector = make_detector(monkeypatch, raw_grid([], nc=2), tmp_path)
        dets = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        assert dets.boxes.shape == (0, 4) and dets.scores.shape == (0,) and dets.class_ids.shape == (0,)


# --- run_stage (fake session + synthetic clip) -----------------------------------


def make_ctx(clip: Path, workdir: Path, **settings_overrides) -> StageContext:
    settings = BasketballSettings(workdir=str(workdir), **settings_overrides)
    clip_id = compute_clip_id(clip)
    return StageContext(
        stage="detect",
        clip_path=clip,
        clip_id=clip_id,
        settings=settings,
        cache=ClipCache(workdir, clip_id),
    )


@pytest.mark.unit
class TestRunStage:
    def test_stage_writes_npz_and_output_json(self, monkeypatch, cfr_clip, tmp_path):
        monkeypatch.setattr(detect, "ort", fake_ort(raw_grid(TestDetectorDecoding.DETS, nc=2), COCO_NAMES_META))
        model = tmp_path / "fake.onnx"
        model.write_bytes(b"fake model bytes")
        ctx = make_ctx(
            cfr_clip,
            tmp_path / "work",
            base_fps=8.0,
            detect_model_path=str(model),
            detect_classes=SMOKE_CLASS_MAP,
            detect_threads=1,
        )
        run_stage_by_name("detect", ctx)

        assert ctx.cache.is_warm("detect")
        out = ctx.cache.read_json("detect")
        arrays = ctx.cache.read_arrays("detect")  # npz round-trip through the cache

        # model section
        assert out["model"]["path"] == str(model)
        assert out["model"]["sha256"] == hashlib.sha256(b"fake model bytes").hexdigest()
        assert out["model"]["input_size"] == [INPUT, INPUT]
        assert out["model"]["classes"][:6] == list(CANONICAL_CLASSES)

        # frames: every sampled frame present, 2 detections each (person + ball)
        num_frames = len(out["frames"])
        assert num_frames > 0
        assert all(f["n_dets"] == 2 for f in out["frames"])
        assert out["counts_by_class"]["player"] == num_frames
        assert out["counts_by_class"]["ball"] == num_frames
        assert out["counts_by_class"]["rim"] == 0
        assert out["timing"]["ms_per_frame_avg"] > 0
        assert out["npz"] == "arrays.npz"

        # npz layout: flat detection arrays + frame_t, aligned by frame_idx
        m, f = 2 * num_frames, num_frames
        assert arrays["boxes"].shape == (m, 4) and arrays["boxes"].dtype == np.float32
        assert arrays["scores"].shape == (m,) and arrays["scores"].dtype == np.float32
        assert arrays["class_ids"].shape == (m,) and arrays["class_ids"].dtype == np.int32
        assert arrays["frame_idx"].shape == (m,) and arrays["frame_idx"].dtype == np.int32
        assert arrays["frame_t"].shape == (f,) and arrays["frame_t"].dtype == np.float64
        assert (np.diff(arrays["frame_t"]) > 0).all()
        np.testing.assert_array_equal(np.unique(arrays["frame_idx"]), np.arange(f))
        # frames meta t matches frame_t
        np.testing.assert_allclose([fr["t"] for fr in out["frames"]], arrays["frame_t"], atol=1e-5)
        # per-frame slice: frame 0 has exactly one player and one ball
        first = arrays["class_ids"][arrays["frame_idx"] == 0]
        assert sorted(first.tolist()) == [0, 3]

    def test_no_detections_still_writes_valid_empty_arrays(self, monkeypatch, cfr_clip, tmp_path):
        monkeypatch.setattr(detect, "ort", fake_ort(raw_grid([], nc=2), COCO_NAMES_META))
        model = tmp_path / "fake.onnx"
        model.write_bytes(b"x")
        ctx = make_ctx(cfr_clip, tmp_path / "work", detect_model_path=str(model), detect_classes=SMOKE_CLASS_MAP)
        run_stage_by_name("detect", ctx)
        out = ctx.cache.read_json("detect")
        arrays = ctx.cache.read_arrays("detect")
        assert arrays["boxes"].shape == (0, 4)
        assert arrays["frame_t"].shape[0] == len(out["frames"]) > 0
        assert all(f["n_dets"] == 0 for f in out["frames"])
        assert set(out["counts_by_class"].values()) == {0}


@pytest.mark.unit
class TestModelPathErrors:
    def test_empty_model_path_raises_with_readme_pointer(self, cfr_clip, tmp_path):
        ctx = make_ctx(cfr_clip, tmp_path / "work", detect_model_path="")
        with pytest.raises(RuntimeError, match="models/README.md"):
            run_stage_by_name("detect", ctx)
        assert not ctx.cache.is_warm("detect")

    def test_missing_model_file_raises_with_readme_pointer(self, cfr_clip, tmp_path):
        ctx = make_ctx(cfr_clip, tmp_path / "work", detect_model_path=str(tmp_path / "nope.onnx"))
        with pytest.raises(FileNotFoundError, match="models/README.md"):
            run_stage_by_name("detect", ctx)


# --- Integration: real COCO smoke-test ONNX --------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not COCO_ONNX_640.is_file(),
    reason="COCO smoke-test ONNX absent — see libs/basketball/models/README.md",
)
class TestCocoOnnxSmoke:
    def test_wrapper_end_to_end_on_real_model(self):
        detector = YoloOnnxDetector(COCO_ONNX_640, conf=0.25, class_map=SMOKE_CLASS_MAP, threads=2)
        assert detector.input_size == (640, 640)  # static export wins over default 960
        assert detector.model_names is not None and detector.model_names[0] == "person"
        assert detector.class_names[:6] == list(CANONICAL_CLASSES)
        rng = np.random.default_rng(0)
        frame = rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)
        dets = detector.detect(frame)  # noise frame: mostly checking dtypes/shapes/no crash
        assert dets.boxes.dtype == np.float32 and dets.boxes.shape[1] == 4
        assert dets.scores.shape == dets.class_ids.shape == (dets.boxes.shape[0],)
        if dets.boxes.shape[0]:
            assert (dets.boxes[:, [0, 2]] <= 1280).all() and (dets.boxes[:, [1, 3]] <= 720).all()

    def test_stage_end_to_end_on_synthetic_clip(self, cfr_clip, tmp_path):
        ctx = make_ctx(
            cfr_clip,
            tmp_path / "work",
            base_fps=4.0,
            detect_model_path=str(COCO_ONNX_640),
            detect_threads=2,
        )
        run_stage_by_name("detect", ctx)
        assert ctx.cache.is_warm("detect")
        out = ctx.cache.read_json("detect")
        arrays = ctx.cache.read_arrays("detect")
        assert out["model"]["input_size"] == [640, 640]
        assert out["model"]["classes"][:6] == list(CANONICAL_CLASSES)
        assert len(out["model"]["sha256"]) == 64
        assert len(out["frames"]) == arrays["frame_t"].shape[0] > 0
        assert sum(f["n_dets"] for f in out["frames"]) == arrays["boxes"].shape[0]
        assert out["timing"]["ms_per_frame_avg"] > 0
