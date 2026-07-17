"""Player tracking + team clustering — Epic 3 story 1 (Signal C, part 1).

Implements the ``teams`` pipeline stage (see libs/basketball/stages.py):
ByteTrack (via ``supervision``) over the detect stage's player detections,
with the shared camera-cut detector (libs/basketball/cuts.py) resetting the
tracker so track IDs never bridge a cut, followed by k=2 kit-color
clustering (HSV torso histograms) that assigns every sufficiently long
track to an anonymous team cluster. Cut timestamps in the output are the
midpoint between the two frames spanning the histogram jump.

Clusters are anonymous (0|1) by design — resolving cluster -> team NAME is
the fuse stage's job (it correlates clusters with score-change events).
Cluster numbering is deterministic (cluster 0 = lower mean torso hue, with a
lexicographic centroid tie-break) so reruns agree.

Input (detect stage ``arrays.npz``, aligned on axis 0; canonical class ids
ALWAYS ball=0, rim=1, ball_in_basket=2, player=3, number=4, referee=5)::

    boxes (M, 4) float32 xyxy source px; scores (M,); class_ids (M,) int32;
    frame_idx (M,) int32 -> index into frame_t (F,) float64 (increasing PTS)

Frames are re-decoded on demand via ``sample_frames(clip, base_fps)`` — the
same code path the detect stage used, so frame ``k`` here is exactly the
frame ``frame_idx == k`` indexes.

Cache artifacts written by ``run_stage`` (under ``<workdir>/<clip_id>/teams/``):

``arrays.npz`` — per-track aggregated kit-color features (debugging aid)::

    track_ids     (T,)  int32
    features      (T, D) float32   # D = H+S+V bins; zero rows where invalid
    feature_valid (T,)  bool

``output.json`` (written last — the warm marker; the EXACT contract the fuse
and jersey stages code against)::

    {clip_id, n_tracks,
     tracks: [{track_id: int, cluster: 0|1|null, cluster_confidence: float,
               det_rows: [int, ...],   # row indices into detect arrays.npz
               t_start: float, t_end: float}],
     cluster_stats: {silhouette: float|null, method: "hsv"},
     cuts: [float, ...]}

``cluster_confidence`` is the per-track centroid-distance margin in [0, 1];
when the clustering silhouette falls below ``teams_min_silhouette`` the
cluster labels are kept but all confidences are scaled down proportionally.
Tracks with fewer than ``teams_min_track_dets`` detections (or no usable
torso pixels) get ``cluster: null`` and confidence 0.0.
"""

import logging
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import supervision as sv

from libs.basketball.cuts import CutTracker
from libs.basketball.video import sample_frames

logger = logging.getLogger(__name__)

# Canonical detect-stage class ids (fixed by libs/basketball/detect.py).
PLAYER_CLASS_ID = 3
REFEREE_CLASS_ID = 5

# Kit-color feature: concatenated per-channel HSV histograms.
H_BINS, S_BINS, V_BINS = 12, 8, 4
FEATURE_DIM = H_BINS + S_BINS + V_BINS

# Torso-pixel extremes mask: very dark (shadow/floor) and blown-out specular
# pixels are dropped before histogramming (white kits sit below 246).
V_MASK_LO, V_MASK_HI = 40, 245
_MIN_MASKED_PIXELS = 16

# ByteTrack parameters (supervision 0.29.1). Activation matches the default
# detect_conf; the lost-track buffer works out to ~1 s at the base fps
# (supervision scales it by frame_rate / 30).
TRACK_ACTIVATION_THRESHOLD = 0.25
LOST_TRACK_BUFFER = 30
MINIMUM_MATCHING_THRESHOLD = 0.8
MINIMUM_CONSECUTIVE_FRAMES = 1

_KMEANS_MAX_ITERS = 100
_PTS_MATCH_TOL = 1e-3


# --- Torso crop & kit-color feature -------------------------------------------


def torso_rect(
    box: np.ndarray, top: float = 0.2, bottom: float = 0.6, inset_x: float = 0.2
) -> Tuple[int, int, int, int]:
    """Torso region of a player box: center-upper portion, as int pixel xyxy.

    ``top``/``bottom`` are fractions of the box height measured from y1;
    ``inset_x`` is the fraction of the box width trimmed from each side.
    Returns (x1, y1, x2, y2); may be empty (x2 <= x1 or y2 <= y1) for
    degenerate boxes.
    """
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    w, h = x2 - x1, y2 - y1
    tx1 = int(round(x1 + w * inset_x))
    tx2 = int(round(x2 - w * inset_x))
    ty1 = int(round(y1 + h * top))
    ty2 = int(round(y1 + h * bottom))
    return tx1, ty1, tx2, ty2


def _hsv_feature(crop_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Normalized HSV histogram feature of one torso crop (None if unusable)."""
    if crop_bgr.size == 0:
        return None
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    v = hsv[:, 2]
    mask = (v >= V_MASK_LO) & (v <= V_MASK_HI)
    pixels = hsv[mask] if int(mask.sum()) >= _MIN_MASKED_PIXELS else hsv
    if pixels.shape[0] == 0:
        return None
    parts = []
    for channel, bins, upper in ((0, H_BINS, 180.0), (1, S_BINS, 256.0), (2, V_BINS, 256.0)):
        hist, _ = np.histogram(pixels[:, channel], bins=bins, range=(0.0, upper))
        total = float(hist.sum())
        parts.append(hist.astype(np.float64) / total if total > 0 else hist.astype(np.float64))
    return np.concatenate(parts)


def torso_feature(
    frame_bgr: np.ndarray,
    box: np.ndarray,
    top: float = 0.2,
    bottom: float = 0.6,
    inset_x: float = 0.2,
) -> Optional[np.ndarray]:
    """Kit-color feature for one player detection (None when the crop is empty)."""
    frame_h, frame_w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = torso_rect(box, top=top, bottom=bottom, inset_x=inset_x)
    x1, y1 = max(x1, 0), max(y1, 0)
    x2, y2 = min(x2, frame_w), min(y2, frame_h)
    if x2 <= x1 or y2 <= y1:
        return None
    return _hsv_feature(frame_bgr[y1:y2, x1:x2])


# Camera-cut detection lives in the shared libs/basketball/cuts.py module
# (CutTracker) — the same detector the shots stage uses via detect_cuts().


# --- k=2 clustering (deterministic, numpy-only) --------------------------------


@dataclass
class ClusterResult:
    """k=2 clustering over per-track features, with deterministic numbering."""

    labels: np.ndarray  # (E,) int, values 0|1
    confidences: np.ndarray  # (E,) float in [0, 1], silhouette-gated margins
    silhouette: float


def _pairwise_dist(x: np.ndarray) -> np.ndarray:
    diff = x[:, None, :] - x[None, :, :]
    return np.sqrt((diff * diff).sum(axis=2))


def _kmeans2(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Deterministic 2-means: farthest-pair init + Lloyd iterations."""
    dist = _pairwise_dist(x)
    i, j = np.unravel_index(int(np.argmax(dist)), dist.shape)
    if dist[i, j] <= 0.0:  # all points identical -> degenerate single cluster
        return np.zeros(x.shape[0], dtype=int), np.stack([x[0], x[0]])
    centroids = np.stack([x[i], x[j]])
    labels = np.full(x.shape[0], -1, dtype=int)
    for _ in range(_KMEANS_MAX_ITERS):
        d = np.linalg.norm(x[:, None, :] - centroids[None, :, :], axis=2)  # (n, 2)
        new_labels = np.argmin(d, axis=1)
        new_centroids = centroids.copy()
        for k in (0, 1):
            members = new_labels == k
            if members.any():
                new_centroids[k] = x[members].mean(axis=0)
        if np.array_equal(new_labels, labels) and np.allclose(new_centroids, centroids):
            break
        labels, centroids = new_labels, new_centroids
    return labels, centroids


def _mean_hue(centroid: np.ndarray) -> float:
    """Mean hue (degrees, 0-180 OpenCV scale) of a centroid's H-histogram part."""
    weights = centroid[:H_BINS]
    total = float(weights.sum())
    if total <= 1e-12:
        return float("inf")
    centers = (np.arange(H_BINS) + 0.5) * (180.0 / H_BINS)
    return float((centers * weights).sum() / total)


def _silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    """Mean silhouette score (euclidean); singleton-cluster samples score 0."""
    dist = _pairwise_dist(x)
    scores = np.zeros(x.shape[0])
    for i in range(x.shape[0]):
        same = labels == labels[i]
        same[i] = False
        other = labels != labels[i]
        if not same.any() or not other.any():
            continue  # singleton cluster -> 0 by convention
        a = float(dist[i, same].mean())
        b = float(dist[i, other].mean())
        m = max(a, b)
        scores[i] = (b - a) / m if m > 0 else 0.0
    return float(scores.mean())


def cluster_tracks(features: np.ndarray, min_silhouette: float) -> ClusterResult:
    """k=2 KMeans over per-track features -> deterministic labels + confidences.

    Cluster 0 is the cluster with the lower centroid mean hue (lexicographic
    centroid tie-break), so numbering is stable across reruns and input
    orderings. Confidences are centroid-distance margins; when the silhouette
    falls below ``min_silhouette`` they are scaled down proportionally
    (clusters stay assigned — the low silhouette itself is reported).
    """
    x = np.asarray(features, dtype=np.float64)
    labels, centroids = _kmeans2(x)
    if len(np.unique(labels)) < 2:
        return ClusterResult(labels=labels, confidences=np.zeros(x.shape[0]), silhouette=0.0)

    def order_key(c: np.ndarray) -> Tuple[float, Tuple[float, ...]]:
        return (_mean_hue(c), tuple(np.round(c, 9)))

    if order_key(centroids[1]) < order_key(centroids[0]):
        labels = 1 - labels
        centroids = centroids[::-1]

    silhouette = _silhouette(x, labels)
    d = np.linalg.norm(x[:, None, :] - centroids[None, :, :], axis=2)  # (n, 2)
    own = d[np.arange(x.shape[0]), labels]
    other = d[np.arange(x.shape[0]), 1 - labels]
    denom = own + other
    margins = np.where(denom > 1e-12, (other - own) / np.maximum(denom, 1e-12), 0.0).clip(0.0, 1.0)
    if min_silhouette > 0 and silhouette < min_silhouette:
        margins = margins * max(silhouette, 0.0) / min_silhouette
    return ClusterResult(labels=labels, confidences=margins, silhouette=silhouette)


# --- Tracking ------------------------------------------------------------------


@dataclass
class _Track:
    det_rows: List[int] = field(default_factory=list)
    ts: List[float] = field(default_factory=list)
    feats: List[Optional[np.ndarray]] = field(default_factory=list)


def _make_tracker(frame_rate: float) -> sv.ByteTrack:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)  # deprecated in sv 0.30; pinned to 0.29.1
        return sv.ByteTrack(
            track_activation_threshold=TRACK_ACTIVATION_THRESHOLD,
            lost_track_buffer=LOST_TRACK_BUFFER,
            minimum_matching_threshold=MINIMUM_MATCHING_THRESHOLD,
            frame_rate=frame_rate,
            minimum_consecutive_frames=MINIMUM_CONSECUTIVE_FRAMES,
        )


def _effective_fps(frame_t: np.ndarray, fallback: float) -> float:
    """Sampling rate implied by the detect stage's PTS timestamps (dt median)."""
    if frame_t.shape[0] >= 2:
        median_dt = float(np.median(np.diff(frame_t)))
        if median_dt > 0:
            return 1.0 / median_dt
    return fallback


def _rows_by_frame(frame_idx: np.ndarray, num_frames: int) -> List[np.ndarray]:
    """Detection-row indices grouped per frame index (rows ascending)."""
    order = np.argsort(frame_idx, kind="stable")
    sorted_fi = frame_idx[order]
    starts = np.searchsorted(sorted_fi, np.arange(num_frames), side="left")
    ends = np.searchsorted(sorted_fi, np.arange(num_frames), side="right")
    return [np.sort(order[starts[k] : ends[k]]) for k in range(num_frames)]


def _aggregate_feature(feats: List[Optional[np.ndarray]], max_samples: int) -> Optional[np.ndarray]:
    """Mean of up to ``max_samples`` well-spread valid per-detection features."""
    valid = [f for f in feats if f is not None]
    if not valid:
        return None
    n = len(valid)
    idx = np.unique(np.linspace(0, n - 1, num=min(n, max(max_samples, 1))).round().astype(int))
    agg = np.mean([valid[i] for i in idx], axis=0)
    total = float(agg.sum())
    return agg / total * 3.0 if total > 0 else None  # 3 unit sub-histograms


# --- Pipeline stage --------------------------------------------------------------


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``teams`` stage: track players, reset at cuts, cluster kits into 2 teams.

    When the detect stage was skipped (its output.json is a
    ``{"skipped": true}`` marker — no model configured), this stage writes
    its own skipped marker and no-ops; fuse treats it as absent."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    settings = ctx.settings
    try:
        detect_out = ctx.cache.read_json("detect")
    except FileNotFoundError:
        detect_out = {}
    if isinstance(detect_out, dict) and detect_out.get("skipped"):
        logger.warning("teams: detect stage was skipped (%s) — no players to track", detect_out.get("reason"))
        ctx.cache.write_json(
            ctx.stage,
            {"clip_id": ctx.clip_id, "skipped": True, "reason": "detect stage was skipped — no detections"},
        )
        return
    arrs = ctx.cache.read_arrays("detect")
    for key in ("boxes", "scores", "class_ids", "frame_idx", "frame_t"):
        if key not in arrs:
            raise ValueError(f"teams stage: detect arrays.npz is missing '{key}' (clip {ctx.clip_id})")
    boxes = arrs["boxes"].astype(np.float32).reshape(-1, 4)
    scores = arrs["scores"].astype(np.float32).reshape(-1)
    class_ids = arrs["class_ids"].astype(np.int32).reshape(-1)
    frame_idx = arrs["frame_idx"].astype(np.int64).reshape(-1)
    frame_t = arrs["frame_t"].astype(np.float64).reshape(-1)
    num_frames = frame_t.shape[0]
    rows_per_frame = _rows_by_frame(frame_idx, num_frames)

    tracker = _make_tracker(_effective_fps(frame_t, settings.base_fps))
    tracks: Dict[int, _Track] = {}
    id_map: Dict[Tuple[int, int], int] = {}  # (segment, raw ByteTrack id) -> global id
    segment = 0
    next_id = 1
    cut_tracker = CutTracker(settings.teams_cut_threshold)
    frames_seen = 0

    for k, (t, frame) in enumerate(sample_frames(ctx.clip_path, settings.base_fps)):
        if k >= num_frames or abs(t - frame_t[k]) > _PTS_MATCH_TOL:
            raise RuntimeError(
                f"teams stage: sampled frame {k} (t={t:.3f}) does not match the detect cache "
                f"for clip {ctx.clip_id} — re-run the detect stage (--force)."
            )
        frames_seen += 1

        if cut_tracker.update(float(t), frame):
            tracker.reset()  # raw ids restart at 1; (segment, raw) keeps globals unique
            segment += 1

        rows = rows_per_frame[k]
        rows = rows[class_ids[rows] == PLAYER_CLASS_ID]  # players only; referees (5) excluded
        detections = sv.Detections(
            xyxy=boxes[rows].reshape(-1, 4),
            confidence=scores[rows],
            class_id=np.full(rows.shape[0], PLAYER_CLASS_ID, dtype=int),
            data={"det_row": rows.astype(np.int64)},
        )
        tracked = tracker.update_with_detections(detections)
        tracker_ids = tracked.tracker_id if tracked.tracker_id is not None else np.zeros(0, dtype=int)
        for i in range(len(tracked)):
            raw_id = int(tracker_ids[i])
            gid = id_map.get((segment, raw_id))
            if gid is None:
                gid = next_id
                next_id += 1
                id_map[(segment, raw_id)] = gid
                tracks[gid] = _Track()
            feat = torso_feature(
                frame,
                tracked.xyxy[i],
                top=settings.teams_torso_top,
                bottom=settings.teams_torso_bottom,
                inset_x=settings.teams_torso_inset_x,
            )
            track = tracks[gid]
            track.det_rows.append(int(tracked.data["det_row"][i]))
            track.ts.append(float(t))
            track.feats.append(feat)

    if frames_seen != num_frames:
        raise RuntimeError(
            f"teams stage: sampled {frames_seen} frames but the detect cache has {num_frames} "
            f"for clip {ctx.clip_id} — re-run the detect stage (--force)."
        )

    # --- Per-track features + clustering ---
    track_ids = sorted(tracks)
    agg_features: Dict[int, Optional[np.ndarray]] = {
        gid: _aggregate_feature(tracks[gid].feats, settings.teams_max_samples) for gid in track_ids
    }
    eligible = [
        gid
        for gid in track_ids
        if len(tracks[gid].det_rows) >= settings.teams_min_track_dets and agg_features[gid] is not None
    ]
    cluster_by_gid: Dict[int, int] = {}
    confidence_by_gid: Dict[int, float] = {}
    silhouette: Optional[float] = None
    if len(eligible) >= 2:
        result = cluster_tracks(
            np.stack([agg_features[gid] for gid in eligible]),  # type: ignore[arg-type]
            min_silhouette=settings.teams_min_silhouette,
        )
        silhouette = round(float(result.silhouette), 4)
        for gid, label, conf in zip(eligible, result.labels, result.confidences):
            cluster_by_gid[gid] = int(label)
            confidence_by_gid[gid] = float(conf)

    # --- Stage artifacts: npz first, output.json last (the warm marker) ---
    features_matrix = np.zeros((len(track_ids), FEATURE_DIM), dtype=np.float32)
    feature_valid = np.zeros(len(track_ids), dtype=bool)
    for row, gid in enumerate(track_ids):
        feat = agg_features[gid]
        if feat is not None:
            features_matrix[row] = feat.astype(np.float32)
            feature_valid[row] = True
    ctx.cache.write_arrays(
        ctx.stage,
        {
            "track_ids": np.asarray(track_ids, dtype=np.int32),
            "features": features_matrix,
            "feature_valid": feature_valid,
        },
    )

    track_entries = []
    for gid in track_ids:
        track = tracks[gid]
        order = np.argsort(track.det_rows)
        track_entries.append(
            {
                "track_id": gid,
                "cluster": cluster_by_gid.get(gid),
                "cluster_confidence": round(confidence_by_gid.get(gid, 0.0), 4),
                "det_rows": [int(track.det_rows[i]) for i in order],
                "t_start": round(min(track.ts), 6),
                "t_end": round(max(track.ts), 6),
            }
        )
    ctx.cache.write_json(
        ctx.stage,
        {
            "clip_id": ctx.clip_id,
            "n_tracks": len(track_entries),
            "tracks": track_entries,
            "cluster_stats": {"silhouette": silhouette, "method": "hsv"},
            "cuts": cut_tracker.cuts,
        },
    )
