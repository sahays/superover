"""Ball/rim/player detection — YOLO ONNX CPU inference (Epic 2, Signal B).

Implements the ``detect`` pipeline stage (see libs/basketball/stages.py): a
generic onnxruntime YOLO wrapper (letterbox preprocessing, raw-grid + NMS or
end-to-end NMS-free decoding, per-class confidence thresholds) run over the
base-fps frame sample of a clip. Model acquisition is documented in
libs/basketball/models/README.md; the model path comes from
``BASKETBALL_DETECT_MODEL_PATH``.

Canonical detection classes (downstream stages key on these names/ids)::

    id 0  ball
    id 1  rim
    id 2  ball_in_basket
    id 3  player
    id 4  number
    id 5  referee

Model class names are translated to these roles via the
``detect_classes`` setting; unmapped model classes pass through under their
own name and get ids >= 6 (the full id -> name table is written to
``output.json["model"]["classes"]``). Ids 0-5 are ALWAYS the canonical six,
in the order above, regardless of model.

Cache artifacts written by ``run_stage`` (under ``<workdir>/<clip_id>/detect/``):

``arrays.npz`` — flat per-detection arrays, aligned on axis 0 (M = total
detections across all sampled frames, F = number of sampled frames)::

    boxes      (M, 4) float32  x1, y1, x2, y2 in source-video pixels
    scores     (M,)   float32  post-NMS confidence in [0, 1]
    class_ids  (M,)   int32    index into output.json["model"]["classes"]
    frame_idx  (M,)   int32    index into frame_t (and output.json["frames"])
    frame_t    (F,)   float64  PTS seconds of each sampled frame (base_fps)

Detections for sampled frame ``k`` are the rows where ``frame_idx == k``;
frames with no detections simply have no rows. All frames sampled from the
clip appear in ``frame_t`` in decode order (strictly increasing).

``output.json`` (written last — the warm marker)::

    {
      "clip_id": str,
      "model": {"path": str, "sha256": str, "input_size": [h, w],
                 "classes": [str, ...]},        # index == class id in the npz
      "frames": [{"t": float, "n_dets": int}, ...],   # aligned with frame_t
      "counts_by_class": {class_name: int, ...},      # canonical roles always
                                                      # present; pass-through
                                                      # classes only if detected
      "timing": {"ms_per_frame_avg": float},
      "npz": "arrays.npz"
    }

Skipped marker: a default full-pipeline run with no configured model writes
``output.json`` as ``{"clip_id": str, "skipped": true, "reason": str}`` and
NO arrays.npz — consumers must check ``skipped`` before reading arrays (see
``run_stage``).

Typical consumption (shots/teams/jersey stages)::

    out = ctx.cache.read_json("detect")
    arrs = ctx.cache.read_arrays("detect")           # arrays.npz
    ball_id = out["model"]["classes"].index("ball")  # always 0
    mask = arrs["class_ids"] == ball_id
    ball_boxes, ball_t = arrs["boxes"][mask], arrs["frame_t"][arrs["frame_idx"][mask]]
"""

import ast
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

import cv2
import numpy as np
import onnxruntime as ort

from libs.basketball.video import sample_frames

logger = logging.getLogger(__name__)

# Canonical roles, in fixed id order (0-5). Downstream code keys on these.
CANONICAL_CLASSES: Tuple[str, ...] = ("ball", "rim", "ball_in_basket", "player", "number", "referee")

PAD_COLOR = 114  # standard YOLO letterbox gray
DEFAULT_IOU = 0.45

_HASH_CHUNK = 1024 * 1024


class Detections(NamedTuple):
    """One frame's detections, in source-video pixel coordinates."""

    boxes: np.ndarray  # (N, 4) float32 xyxy
    scores: np.ndarray  # (N,) float32
    class_ids: np.ndarray  # (N,) int32 — indices into YoloOnnxDetector.class_names


def _empty_detections() -> Detections:
    return Detections(
        boxes=np.zeros((0, 4), dtype=np.float32),
        scores=np.zeros((0,), dtype=np.float32),
        class_ids=np.zeros((0,), dtype=np.int32),
    )


# --- Letterbox geometry -----------------------------------------------------


def letterbox(img: np.ndarray, size: Tuple[int, int]) -> Tuple[np.ndarray, float, Tuple[float, float]]:
    """Resize ``img`` preserving aspect ratio and pad to ``size`` (h, w).

    Returns ``(canvas, scale, (pad_x, pad_y))`` where ``scale`` is the
    source->canvas resize factor and the pads are the top-left offset of the
    image inside the canvas. Padding uses the standard YOLO gray (114).
    """
    in_h, in_w = size
    h, w = img.shape[:2]
    scale = min(in_h / h, in_w / w)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_x = (in_w - new_w) // 2
    pad_y = (in_h - new_h) // 2
    canvas = np.full((in_h, in_w, img.shape[2]), PAD_COLOR, dtype=img.dtype)
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return canvas, scale, (float(pad_x), float(pad_y))


def letterbox_boxes(boxes: np.ndarray, scale: float, pads: Tuple[float, float]) -> np.ndarray:
    """Map xyxy boxes from source pixels into letterboxed-canvas pixels."""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4).copy()
    pad_x, pad_y = pads
    boxes[:, [0, 2]] = boxes[:, [0, 2]] * scale + pad_x
    boxes[:, [1, 3]] = boxes[:, [1, 3]] * scale + pad_y
    return boxes


def unletterbox_boxes(
    boxes: np.ndarray, scale: float, pads: Tuple[float, float], source_hw: Tuple[int, int]
) -> np.ndarray:
    """Map xyxy boxes from letterboxed-canvas pixels back to source pixels (clipped)."""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4).copy()
    pad_x, pad_y = pads
    h, w = source_hw
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / scale
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / scale
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h)
    return boxes


# --- NMS ---------------------------------------------------------------------


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = DEFAULT_IOU) -> np.ndarray:
    """Greedy non-maximum suppression on xyxy boxes; returns kept indices."""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    scores = np.asarray(scores, dtype=np.float32).reshape(-1)
    if boxes.shape[0] == 0:
        return np.zeros((0,), dtype=np.int64)
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1).clip(min=0) * (y2 - y1).clip(min=0)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        ix1 = np.maximum(x1[i], x1[rest])
        iy1 = np.maximum(y1[i], y1[rest])
        ix2 = np.minimum(x2[i], x2[rest])
        iy2 = np.minimum(y2[i], y2[rest])
        inter = (ix2 - ix1).clip(min=0) * (iy2 - iy1).clip(min=0)
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / union, 0.0)
        order = rest[iou <= iou_threshold]
    return np.array(keep, dtype=np.int64)


def _class_aware_nms(boxes: np.ndarray, scores: np.ndarray, class_ids: np.ndarray, iou_threshold: float) -> np.ndarray:
    """NMS applied per class via the coordinate-offset trick; returns kept indices."""
    if boxes.shape[0] == 0:
        return np.zeros((0,), dtype=np.int64)
    stride = float(np.abs(boxes).max()) * 2.0 + 1.0
    offset = class_ids.astype(np.float32)[:, None] * stride
    return nms(boxes + offset, scores, iou_threshold)


# --- Detector ----------------------------------------------------------------


class YoloOnnxDetector:
    """Generic CPU YOLO ONNX detector: letterbox in, source-pixel boxes out.

    Supports both ultralytics export styles:

    * **raw grid** — output ``(1, 4+nc, anchors)`` (or transposed): cxcywh
      boxes + per-class scores; this wrapper applies thresholds and NMS.
    * **end-to-end / NMS-free** — output ``(1, N, 6)`` rows of
      ``x1, y1, x2, y2, score, class_id`` (already NMS'd); this wrapper only
      applies thresholds.

    Class names come from ONNX metadata (``names``) when present, else from
    the ``class_map`` keys in order (id i -> i-th key), else ``class_<i>``.
    Names are translated to canonical roles via ``class_map`` (unknown names
    pass through). ``class_names`` is the id table used by ``Detections``.
    """

    def __init__(
        self,
        model_path: Union[str, Path],
        input_size: int = 960,
        conf: float = 0.25,
        class_map: Optional[Dict[str, str]] = None,
        threads: int = 0,
        iou: float = DEFAULT_IOU,
        per_class_conf: Optional[Dict[str, float]] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.conf = float(conf)
        self.iou = float(iou)
        self.class_map = dict(class_map or {})
        self.per_class_conf = dict(per_class_conf or {})  # canonical role -> threshold

        options = ort.SessionOptions()
        if threads > 0:
            options.intra_op_num_threads = threads
        self.session = ort.InferenceSession(
            str(self.model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )

        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        shape = list(model_input.shape)
        if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
            self.input_size: Tuple[int, int] = (shape[2], shape[3])  # static export wins
        else:
            self.input_size = (int(input_size), int(input_size))

        meta = self.session.get_modelmeta().custom_metadata_map or {}
        # Ultralytics exports declare end2end explicitly; trust it when present
        # (None = unknown -> fall back to the output-shape heuristic).
        raw_end2end = meta.get("end2end")
        self._end2end_meta: Optional[bool] = None if raw_end2end is None else str(raw_end2end).strip().lower() == "true"
        self.model_names = self._parse_names(meta.get("names"))

        # Class-id table: canonical roles first (fixed ids 0-5), extras appended.
        self.class_names: List[str] = list(CANONICAL_CLASSES)
        self._role_to_id: Dict[str, int] = {name: i for i, name in enumerate(self.class_names)}
        self._model_id_to_class_id: Dict[int, int] = {}
        self._threshold_by_model_id: Dict[int, float] = {}
        if self.model_names is not None:
            for model_id in sorted(self.model_names):
                self._class_id_for_model_id(model_id)

    @staticmethod
    def _parse_names(raw: Optional[str]) -> Optional[Dict[int, str]]:
        """Parse ultralytics ``names`` metadata: dict-repr or list-repr string."""
        if not raw:
            return None
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return None
        if isinstance(parsed, dict):
            return {int(k): str(v) for k, v in parsed.items()}
        if isinstance(parsed, (list, tuple)):
            return {i: str(v) for i, v in enumerate(parsed)}
        return None

    def _model_class_name(self, model_id: int) -> str:
        if self.model_names is not None and model_id in self.model_names:
            return self.model_names[model_id]
        map_keys = list(self.class_map)
        if model_id < len(map_keys):
            return map_keys[model_id]
        return f"class_{model_id}"

    def _class_id_for_model_id(self, model_id: int) -> int:
        """Canonical class id for a raw model class id (pass-through ids >= 6)."""
        cached = self._model_id_to_class_id.get(model_id)
        if cached is not None:
            return cached
        role = self.class_map.get(self._model_class_name(model_id), self._model_class_name(model_id))
        if role not in self._role_to_id:
            self._role_to_id[role] = len(self.class_names)
            self.class_names.append(role)
        class_id = self._role_to_id[role]
        self._model_id_to_class_id[model_id] = class_id
        self._threshold_by_model_id[model_id] = float(self.per_class_conf.get(role, self.conf))
        return class_id

    def _threshold_for_model_id(self, model_id: int) -> float:
        self._class_id_for_model_id(model_id)  # populates the threshold cache
        return self._threshold_by_model_id[model_id]

    # --- inference ---

    def detect(self, frame_bgr: np.ndarray) -> Detections:
        """Run the model on one BGR frame; boxes returned in source pixels."""
        source_hw = frame_bgr.shape[:2]
        canvas, scale, pads = letterbox(frame_bgr, self.input_size)
        blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        outputs = self.session.run(None, {self.input_name: np.ascontiguousarray(blob)})
        boxes, scores, model_ids = self._decode(np.asarray(outputs[0], dtype=np.float32))
        if boxes.shape[0] == 0:
            return _empty_detections()
        class_ids = np.array([self._class_id_for_model_id(int(m)) for m in model_ids], dtype=np.int32)
        boxes = unletterbox_boxes(boxes, scale, pads, source_hw)
        return Detections(
            boxes=boxes.astype(np.float32),
            scores=scores.astype(np.float32),
            class_ids=class_ids,
        )

    def _decode(self, raw: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Decode one output tensor -> thresholded, NMS'd (boxes, scores, model class ids).

        Boxes are xyxy in letterboxed-input pixels; coordinate un-mapping is
        the caller's job.
        """
        if self._is_end2end(raw):
            return self._decode_end2end(raw)
        return self._decode_raw_grid(raw)

    def _is_end2end(self, raw: np.ndarray) -> bool:
        if self._end2end_meta is not None:
            return self._end2end_meta
        if raw.ndim == 2:
            return raw.shape[1] == 6
        if raw.ndim == 3:
            # (1, N, 6) is end-to-end; (1, 4+nc, anchors) is a raw grid whose
            # trailing axis is the (large) anchor count. A transposed raw grid
            # with nc == 2 is shape-ambiguous — exports carrying the ultralytics
            # 'end2end' metadata key never hit this heuristic.
            return raw.shape[2] == 6
        return False

    def _decode_end2end(self, raw: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        rows = raw.reshape(-1, raw.shape[-1])
        if rows.shape[1] < 6:
            raise ValueError(f"Unexpected end-to-end detector output shape {raw.shape}; expected rows of 6")
        boxes = rows[:, :4]
        scores = rows[:, 4]
        model_ids = rows[:, 5].astype(np.int64)
        keep = self._threshold_mask(scores, model_ids)
        return boxes[keep], scores[keep], model_ids[keep]

    def _decode_raw_grid(self, raw: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        grid = raw[0] if raw.ndim == 3 else raw
        if grid.ndim != 2:
            raise ValueError(f"Unexpected detector output shape {raw.shape}")
        grid = self._orient_grid(grid)  # -> (anchors, 4+nc)
        if grid.shape[1] <= 4:
            raise ValueError(f"Raw-grid output has no class columns: shape {raw.shape}")
        class_scores = grid[:, 4:]
        model_ids = class_scores.argmax(axis=1)
        scores = class_scores[np.arange(grid.shape[0]), model_ids]
        # Cheap vectorized pre-filter at the loosest threshold, then the exact
        # per-class thresholds on the few survivors.
        candidates = np.nonzero(scores >= self._min_threshold())[0]
        candidates = candidates[self._threshold_mask(scores[candidates], model_ids[candidates])]
        if candidates.size == 0:
            empty = _empty_detections()
            return empty.boxes, empty.scores, empty.class_ids.astype(np.int64)
        boxes = _cxcywh_to_xyxy(grid[candidates, :4])
        scores, model_ids = scores[candidates], model_ids[candidates]
        kept = _class_aware_nms(boxes, scores, model_ids, self.iou)
        return boxes[kept], scores[kept], model_ids[kept]

    def _orient_grid(self, grid: np.ndarray) -> np.ndarray:
        """Return the raw grid as (anchors, 4+nc), whichever way it was exported."""
        if self.model_names is not None:
            channels = 4 + len(self.model_names)
            if grid.shape[0] == channels and grid.shape[1] != channels:
                return grid.T
            if grid.shape[1] == channels:
                return grid
        # Heuristic: the anchor axis is (much) larger than the channel axis.
        return grid.T if grid.shape[0] < grid.shape[1] else grid

    def _min_threshold(self) -> float:
        """The loosest configured threshold (safe vectorized pre-filter)."""
        if not self.per_class_conf:
            return self.conf
        return min(self.conf, *self.per_class_conf.values())

    def _threshold_mask(self, scores: np.ndarray, model_ids: np.ndarray) -> np.ndarray:
        """Boolean keep-mask applying per-class confidence thresholds."""
        if scores.shape[0] == 0:
            return np.zeros((0,), dtype=bool)
        if not self.per_class_conf:
            return scores >= self.conf
        thresholds = np.array([self._threshold_for_model_id(int(m)) for m in model_ids], dtype=np.float32)
        return scores >= thresholds


def _cxcywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    out = np.empty_like(boxes)
    half_w, half_h = boxes[:, 2] / 2.0, boxes[:, 3] / 2.0
    out[:, 0] = boxes[:, 0] - half_w
    out[:, 1] = boxes[:, 1] - half_h
    out[:, 2] = boxes[:, 0] + half_w
    out[:, 3] = boxes[:, 1] + half_h
    return out


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


# --- Pipeline stage ----------------------------------------------------------


def build_detector(settings) -> YoloOnnxDetector:
    """Construct the detector from BasketballSettings, validating the model path."""
    model_path = settings.detect_model_path
    if not model_path:
        raise RuntimeError(
            "detect stage: no detection model configured. Set BASKETBALL_DETECT_MODEL_PATH "
            "to a YOLO ONNX file — see libs/basketball/models/README.md for how to train the "
            "basketball model or produce the COCO smoke-test fallback."
        )
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"detect stage: detection model not found at '{path}'. Check "
            "BASKETBALL_DETECT_MODEL_PATH — see libs/basketball/models/README.md for how to "
            "obtain a model."
        )
    return YoloOnnxDetector(
        path,
        input_size=settings.detect_input_size,
        conf=settings.detect_conf,
        class_map=settings.detect_classes,
        threads=settings.detect_threads,
    )


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``detect`` stage: YOLO detections for every base-fps sampled frame.

    Writes ``arrays.npz`` then ``output.json`` (see module docstring for the
    exact layouts; output.json is written last as the warm marker).

    Graceful degradation (HLD rule): when no model is configured
    (``detect_model_path`` empty) and the stage runs as part of the CLI's
    default full-pipeline sweep (``ctx.pipeline``), it writes a skipped
    marker ``{"clip_id", "skipped": true, "reason": ...}`` — no arrays.npz —
    and logs a warning; downstream stages then no-op and fuse produces
    scorebug-only events. A direct invocation (``--stage detect`` or a bare
    ``run_stage`` call) still raises the instructive RuntimeError.
    """
    if not ctx.settings.detect_model_path and getattr(ctx, "pipeline", False):
        reason = (
            "no detection model configured (BASKETBALL_DETECT_MODEL_PATH is empty); "
            "see libs/basketball/models/README.md for how to obtain one"
        )
        logger.warning(
            "detect: %s — skipping detection; shots/teams/jersey will no-op and fuse will be scorebug-only",
            reason,
        )
        ctx.cache.write_json(ctx.stage, {"clip_id": ctx.clip_id, "skipped": True, "reason": reason})
        return

    detector = build_detector(ctx.settings)

    all_boxes: List[np.ndarray] = []
    all_scores: List[np.ndarray] = []
    all_class_ids: List[np.ndarray] = []
    all_frame_idx: List[np.ndarray] = []
    frame_t: List[float] = []
    frames_meta: List[Dict[str, Union[float, int]]] = []
    total_ms = 0.0

    for frame_index, (t, frame) in enumerate(sample_frames(ctx.clip_path, ctx.settings.base_fps)):
        start = time.perf_counter()
        dets = detector.detect(frame)
        total_ms += (time.perf_counter() - start) * 1000.0
        n = int(dets.boxes.shape[0])
        all_boxes.append(dets.boxes)
        all_scores.append(dets.scores)
        all_class_ids.append(dets.class_ids)
        all_frame_idx.append(np.full((n,), frame_index, dtype=np.int32))
        frame_t.append(t)
        frames_meta.append({"t": round(t, 6), "n_dets": n})

    num_frames = len(frame_t)
    class_ids = np.concatenate(all_class_ids) if all_class_ids else np.zeros((0,), dtype=np.int32)
    arrays = {
        "boxes": np.concatenate(all_boxes) if all_boxes else np.zeros((0, 4), dtype=np.float32),
        "scores": np.concatenate(all_scores) if all_scores else np.zeros((0,), dtype=np.float32),
        "class_ids": class_ids,
        "frame_idx": np.concatenate(all_frame_idx) if all_frame_idx else np.zeros((0,), dtype=np.int32),
        "frame_t": np.asarray(frame_t, dtype=np.float64),
    }
    ctx.cache.write_arrays(ctx.stage, arrays)

    # Canonical roles always reported (zeros matter downstream); pass-through
    # classes only when actually detected, to keep output.json readable.
    counts_by_class = {
        name: int((class_ids == class_id).sum())
        for class_id, name in enumerate(detector.class_names)
        if class_id < len(CANONICAL_CLASSES) or (class_ids == class_id).any()
    }
    ctx.cache.write_json(
        ctx.stage,
        {
            "clip_id": ctx.clip_id,
            "model": {
                "path": str(detector.model_path),
                "sha256": _file_sha256(detector.model_path),
                "input_size": list(detector.input_size),
                "classes": list(detector.class_names),
            },
            "frames": frames_meta,
            "counts_by_class": counts_by_class,
            "timing": {"ms_per_frame_avg": round(total_ms / num_frames, 2) if num_frames else 0.0},
            "npz": "arrays.npz",
        },
    )
