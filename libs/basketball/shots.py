"""Ball-through-rim make/miss analysis — the ``shots`` stage (Epic 2 story 3, Signal B).

Consumes the ``detect`` stage cache (base-fps ball / rim / ball-in-basket
detections) and turns rim-neighborhood ball trajectories into shot
candidates. Detection ran at base fps only, so classification works from
base-fps samples + geometry, tolerating occlusion gaps of a few samples
(the ball vanishes behind rim, net, or players).

Per-clip pipeline:

1. **Camera cuts** via the shared HSV-histogram total-variation detector
   (libs/basketball/cuts.py) -> cut timestamps -> camera segments.
2. **Rim tracking**: rim detections (class ``rim``) clustered into persistent
   rim boxes per camera segment (rims are static between cuts); 0, 1, or 2+
   rims per segment all handled.
3. **Trajectory episodes**: each ball detection (class ``ball``) inside a
   rim's neighborhood (rim box expanded ``shots_rim_neighborhood`` x) joins
   that rim's episode; gaps up to ``shots_gap_max_samples`` samples are
   bridged. Episodes classify as:

   * ``make``   — ball center above the rim plane inside the rim x-range in
     one sample, then below the plane inside the *inner*-rim x-range within
     ``shots_pass_window_sec`` worth of samples. No approach-speed
     requirement, so slow free-throw drops classify.
   * ``miss``   — approach + departure without pass-through: the ball fell
     past the rim plane nearby or came within ``shots_miss_proximity`` x of
     the rim box. Front-rim dips below the plane OUTSIDE the inner x-range
     (roll-outs) land here, never as makes.
   * ``unknown`` — the ball crossed the neighborhood without shot-like
     geometry (e.g. a flat pass); fusion emits nothing for these unless a
     score delta confirms them.

4. **ball_in_basket** detections (class 2) fold in as strong make evidence
   with their own ``t``: merged into an overlapping same-rim candidate
   (forcing ``kind: make``) or emitted as a standalone make candidate.
5. **Replay guard**: candidates whose window spans a camera cut are marked
   ``suppressed`` (fusion must ignore them); a same-kind candidate repeating
   in a *different* segment within ``shots_replay_window_sec`` is flagged
   ``possible_replay`` rather than dropped (fusion drops it only when no
   score delta confirms it).

output.json schema (the ``fuse`` stage codes against this)::

    {
      "clip_id": str,
      "fps_estimate": float,          # median sample rate from detect frame_t
      "cuts": [float, ...],           # camera-cut timestamps (sec, PTS)
      "segments": [[t0, t1], ...],    # camera segments covering the clip
      "rims": [
        {"rim_id": int, "segment": int, "box": [x1, y1, x2, y2],
         "n_dets": int, "t_first": float, "t_last": float}, ...
      ],
      "shot_candidates": [            # sorted by t
        {"candidate_id": int,
         "kind": "make" | "miss" | "unknown",  # ball_in_basket forces "make"
         "trajectory_kind": "make" | "miss" | "unknown" | null,  # geometry
         "signals": [...],            # subset of ["trajectory", "ball_in_basket"]
         "t": float,                  # best event time (= t_rim when known)
         "t_rim": float | null,       # interpolated rim-plane crossing time
         "window": [t0, t1],          # first..last contributing observation
         "segment": int,
         "rim_id": int | null,        # null only for rimless bib candidates
         "confidence": float,
         "det_rows": [int, ...],      # rows into detect arrays.npz
         "last_ball": {"t": float, "center": [x, y], "det_row": int} | null,
         "nearest_player_det_row": int | null,  # shooter hint for fusion
         "suppressed": bool,          # window spans a cut -> fusion ignores
         "possible_replay": bool},
        ...
      ],
      "params": {...}                 # settings snapshot used for this run
    }
"""

import logging
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from libs.basketball.cuts import detect_cuts  # noqa: F401  (re-export: stage API + tests)

logger = logging.getLogger(__name__)

# Canonical detect-stage class ids (libs/basketball/detect.py — ALWAYS 0-5).
CLASS_BALL = 0
CLASS_RIM = 1
CLASS_BALL_IN_BASKET = 2
CLASS_PLAYER = 3

# ball_in_basket detections closer than this (sec) group into one candidate.
BIB_GROUP_GAP_SEC = 0.75
# A bib group merges into a trajectory candidate when their windows overlap
# after padding by this many seconds.
BIB_MERGE_PAD_SEC = 0.75
# Nearest-player search widens up to this many base-fps frames from the ball.
PLAYER_SEARCH_FRAMES = 4


# ---------------------------------------------------------------------------
# Camera cuts — shared detector in libs/basketball/cuts.py (``detect_cuts``
# is re-exported above); segment helpers below stay local to this stage.
# ---------------------------------------------------------------------------


def segment_index(t: float, cuts: Sequence[float]) -> int:
    """Index of the camera segment containing time ``t`` (cuts sorted)."""
    return bisect_right(list(cuts), t)


def segments_from_cuts(cuts: Sequence[float], t_start: float, t_end: float) -> List[List[float]]:
    """[t0, t1] spans of every camera segment covering [t_start, t_end]."""
    if t_end < t_start:
        return []
    bounds = [t_start] + [c for c in sorted(cuts)] + [t_end]
    return [[round(a, 6), round(b, 6)] for a, b in zip(bounds[:-1], bounds[1:])]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _expand_box(box: Sequence[float], factor: float) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    hw, hh = (x2 - x1) / 2.0 * factor, (y2 - y1) / 2.0 * factor
    return cx - hw, cy - hh, cx + hw, cy + hh


def _contains(box: Tuple[float, float, float, float], x: float, y: float) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


@dataclass
class _BallObs:
    """One base-fps ball observation assigned to a rim."""

    row: int  # row into detect arrays.npz
    fidx: int  # frame index (into frame_t)
    t: float
    cx: float
    cy: float


# ---------------------------------------------------------------------------
# Rim clustering
# ---------------------------------------------------------------------------


def cluster_rims(
    boxes: np.ndarray,
    ts: np.ndarray,
    cuts: Sequence[float],
    min_dets: int,
) -> List[Dict[str, Any]]:
    """Cluster rim detections into persistent per-segment rim boxes.

    Rims are static between camera cuts, so a greedy center-distance
    clustering per segment suffices; the cluster box is the per-coordinate
    median. Clusters with fewer than ``min_dets`` members are noise.
    """
    clusters: List[Dict[str, Any]] = []
    for box, t in sorted(zip(boxes.tolist(), ts.tolist()), key=lambda item: item[1]):
        seg = segment_index(t, cuts)
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        width = box[2] - box[0]
        best = None
        best_dist = None
        for cluster in clusters:
            if cluster["segment"] != seg:
                continue
            ccx, ccy = cluster["center"]
            dist = float(np.hypot(cx - ccx, cy - ccy))
            if dist <= max(cluster["width"], width) and (best_dist is None or dist < best_dist):
                best, best_dist = cluster, dist
        if best is None:
            clusters.append({"segment": seg, "boxes": [box], "ts": [t], "center": (cx, cy), "width": width})
        else:
            best["boxes"].append(box)
            best["ts"].append(t)
            arr = np.asarray(best["boxes"], dtype=np.float64)
            med = np.median(arr, axis=0)
            best["center"] = ((med[0] + med[2]) / 2.0, (med[1] + med[3]) / 2.0)
            best["width"] = float(med[2] - med[0])

    rims: List[Dict[str, Any]] = []
    for cluster in clusters:
        if len(cluster["boxes"]) < min_dets:
            continue
        med = np.median(np.asarray(cluster["boxes"], dtype=np.float64), axis=0)
        rims.append(
            {
                "segment": int(cluster["segment"]),
                "box": [round(float(v), 2) for v in med],
                "n_dets": len(cluster["boxes"]),
                "t_first": round(min(cluster["ts"]), 6),
                "t_last": round(max(cluster["ts"]), 6),
            }
        )
    rims.sort(key=lambda r: (r["segment"], r["box"][0]))
    for rim_id, rim in enumerate(rims):
        rim["rim_id"] = rim_id
    return rims


# ---------------------------------------------------------------------------
# Trajectory episodes + classification
# ---------------------------------------------------------------------------


def _episodes(obs: List[_BallObs], gap_max_samples: int) -> List[List[_BallObs]]:
    """Split time-ordered observations into episodes, bridging small gaps."""
    episodes: List[List[_BallObs]] = []
    current: List[_BallObs] = []
    for o in obs:
        if current and (o.fidx - current[-1].fidx - 1) > gap_max_samples:
            episodes.append(current)
            current = []
        current.append(o)
    if current:
        episodes.append(current)
    return [ep for ep in episodes if len(ep) >= 2]


def _find_pass_through(
    ep: List[_BallObs],
    rim_box: Sequence[float],
    inner_frac: float,
    pass_max_frames: int,
) -> Optional[Tuple[_BallObs, _BallObs, float, int]]:
    """First adjacent observation pair crossing the rim plane through the
    inner rim: returns (above_obs, below_obs, t_rim, n_missing_samples)."""
    x1, y1, x2, y2 = rim_box
    plane_y = (y1 + y2) / 2.0
    cx = (x1 + x2) / 2.0
    inner_hw = (x2 - x1) * inner_frac / 2.0
    for above, below in zip(ep[:-1], ep[1:]):
        if not (above.cy < plane_y <= below.cy):
            continue
        if below.fidx - above.fidx > pass_max_frames:
            continue
        if not (x1 <= above.cx <= x2):  # above-plane sample inside full rim x-range
            continue
        if not (cx - inner_hw <= below.cx <= cx + inner_hw):  # below inside inner rim
            continue
        frac = (plane_y - above.cy) / (below.cy - above.cy)
        t_rim = above.t + (below.t - above.t) * frac
        return above, below, t_rim, below.fidx - above.fidx - 1
    return None


def _closest_approach(ep: List[_BallObs], rim_box: Sequence[float]) -> _BallObs:
    rcx, rcy = (rim_box[0] + rim_box[2]) / 2.0, (rim_box[1] + rim_box[3]) / 2.0
    return min(ep, key=lambda o: float(np.hypot(o.cx - rcx, o.cy - rcy)))


def _fell_past_plane(ep: List[_BallObs], rim_box: Sequence[float]) -> bool:
    """True when some observation sits above the rim plane and a later one
    below it — the ball came down past rim level inside the neighborhood."""
    plane_y = (rim_box[1] + rim_box[3]) / 2.0
    seen_above = False
    for o in ep:
        if o.cy < plane_y:
            seen_above = True
        elif seen_above:
            return True
    return False


def _classify_episode(ep: List[_BallObs], rim_box: Sequence[float], settings, fps: float) -> Dict[str, Any]:
    """Classify one episode -> {kind, t, t_rim, confidence, crossing info}."""
    pass_max_frames = max(2, int(round(fps * settings.shots_pass_window_sec)))
    crossing = _find_pass_through(ep, rim_box, settings.shots_inner_rim_frac, pass_max_frames)
    if crossing is not None:
        above, _below, t_rim, missing = crossing
        confidence = max(0.55, min(0.95, 0.9 - 0.06 * missing))
        return {"kind": "make", "t": t_rim, "t_rim": t_rim, "confidence": confidence, "above_obs": above}

    approach = _closest_approach(ep, rim_box)
    proximity_box = _expand_box(rim_box, settings.shots_miss_proximity)
    reached_rim = any(_contains(proximity_box, o.cx, o.cy) for o in ep)
    if reached_rim or _fell_past_plane(ep, rim_box):
        return {"kind": "miss", "t": approach.t, "t_rim": None, "confidence": 0.7, "above_obs": None}
    return {"kind": "unknown", "t": approach.t, "t_rim": None, "confidence": 0.3, "above_obs": None}


# ---------------------------------------------------------------------------
# Player / ball helpers over the raw detect arrays
# ---------------------------------------------------------------------------


def _nearest_player_row(arrays: Dict[str, np.ndarray], fidx: int, cx: float, cy: float) -> Optional[int]:
    """Row of the player detection nearest (cx, cy), searching outward from
    frame ``fidx`` up to PLAYER_SEARCH_FRAMES frames away."""
    class_ids, frame_idx, boxes = arrays["class_ids"], arrays["frame_idx"], arrays["boxes"]
    player_mask = class_ids == CLASS_PLAYER
    for offset in range(PLAYER_SEARCH_FRAMES + 1):
        frame_mask = np.abs(frame_idx - fidx) == offset
        rows = np.where(player_mask & frame_mask)[0]
        if rows.size == 0:
            continue
        centers_x = (boxes[rows, 0] + boxes[rows, 2]) / 2.0
        centers_y = (boxes[rows, 1] + boxes[rows, 3]) / 2.0
        distances = np.hypot(centers_x - cx, centers_y - cy)
        return int(rows[int(np.argmin(distances))])
    return None


def _last_ball_before(ep: List[_BallObs], t_event: float) -> _BallObs:
    """Last observation at/before the event time (fallback: first obs)."""
    before = [o for o in ep if o.t <= t_event + 1e-9]
    return before[-1] if before else ep[0]


# ---------------------------------------------------------------------------
# Candidate assembly (pure — unit-testable without video or cache)
# ---------------------------------------------------------------------------


def _assign_ball_obs(
    arrays: Dict[str, np.ndarray], rims: List[Dict[str, Any]], neighborhood: float
) -> Dict[int, List[_BallObs]]:
    """Assign each ball detection to the nearest rim whose neighborhood
    contains it; keep one observation per (rim, frame): the nearest ball."""
    class_ids, frame_idx, frame_t, boxes = (
        arrays["class_ids"],
        arrays["frame_idx"],
        arrays["frame_t"],
        arrays["boxes"],
    )
    hoods = [(rim["rim_id"], _expand_box(rim["box"], neighborhood), rim["box"]) for rim in rims]
    per_rim_frame: Dict[Tuple[int, int], _BallObs] = {}
    for row in np.where(class_ids == CLASS_BALL)[0]:
        x1, y1, x2, y2 = (float(v) for v in boxes[row])
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        best_rim = None
        best_dist = None
        for rim_id, hood, rim_box in hoods:
            if not _contains(hood, cx, cy):
                continue
            rcx, rcy = (rim_box[0] + rim_box[2]) / 2.0, (rim_box[1] + rim_box[3]) / 2.0
            dist = float(np.hypot(cx - rcx, cy - rcy))
            if best_dist is None or dist < best_dist:
                best_rim, best_dist = rim_id, dist
        if best_rim is None:
            continue
        fidx = int(frame_idx[row])
        obs = _BallObs(row=int(row), fidx=fidx, t=float(frame_t[fidx]), cx=cx, cy=cy)
        key = (best_rim, fidx)
        existing = per_rim_frame.get(key)
        if existing is None:
            per_rim_frame[key] = obs
        else:
            rim_box = next(r["box"] for r in rims if r["rim_id"] == best_rim)
            rcx, rcy = (rim_box[0] + rim_box[2]) / 2.0, (rim_box[1] + rim_box[3]) / 2.0
            if np.hypot(cx - rcx, cy - rcy) < np.hypot(existing.cx - rcx, existing.cy - rcy):
                per_rim_frame[key] = obs
    by_rim: Dict[int, List[_BallObs]] = {}
    for (rim_id, _fidx), obs in sorted(per_rim_frame.items()):
        by_rim.setdefault(rim_id, []).append(obs)
    return by_rim


def _bib_groups(arrays: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
    """Group ball_in_basket detections that are adjacent in time."""
    class_ids, frame_idx, frame_t, scores = (
        arrays["class_ids"],
        arrays["frame_idx"],
        arrays["frame_t"],
        arrays["scores"],
    )
    rows = [int(r) for r in np.where(class_ids == CLASS_BALL_IN_BASKET)[0]]
    rows.sort(key=lambda r: float(frame_t[int(frame_idx[r])]))
    groups: List[List[int]] = []
    for row in rows:
        t = float(frame_t[int(frame_idx[row])])
        if groups and t - float(frame_t[int(frame_idx[groups[-1][-1]])]) <= BIB_GROUP_GAP_SEC:
            groups[-1].append(row)
        else:
            groups.append([row])
    out = []
    for group in groups:
        ts = [float(frame_t[int(frame_idx[r])]) for r in group]
        best_row = max(group, key=lambda r: float(scores[r]))
        box = arrays["boxes"][best_row]
        out.append(
            {
                "rows": group,
                "t_first": min(ts),
                "t_last": max(ts),
                "t_best": float(frame_t[int(frame_idx[best_row])]),
                "best_row": best_row,
                "best_score": float(scores[best_row]),
                "center": [float((box[0] + box[2]) / 2.0), float((box[1] + box[3]) / 2.0)],
            }
        )
    return out


def _windows_overlap(a0: float, a1: float, b0: float, b1: float, pad: float) -> bool:
    return a0 - pad <= b1 and b0 - pad <= a1


def analyze(arrays: Dict[str, np.ndarray], cuts: Sequence[float], settings) -> Dict[str, Any]:
    """Pure core of the stage: detect arrays + cut list -> shots output dict
    (everything except ``clip_id``)."""
    frame_t = arrays["frame_t"]
    result: Dict[str, Any] = {
        "fps_estimate": float(settings.base_fps),
        "cuts": [round(float(c), 6) for c in cuts],
        "segments": [],
        "rims": [],
        "shot_candidates": [],
        "params": {
            "rim_neighborhood": settings.shots_rim_neighborhood,
            "inner_rim_frac": settings.shots_inner_rim_frac,
            "miss_proximity": settings.shots_miss_proximity,
            "gap_max_samples": settings.shots_gap_max_samples,
            "pass_window_sec": settings.shots_pass_window_sec,
            "min_rim_dets": settings.shots_min_rim_dets,
            "replay_window_sec": settings.shots_replay_window_sec,
            "cut_threshold": settings.shots_cut_threshold,
        },
    }
    if frame_t.size == 0:
        return result
    if frame_t.size > 1:
        result["fps_estimate"] = round(float(1.0 / np.median(np.diff(frame_t))), 3)
    result["segments"] = segments_from_cuts(cuts, float(frame_t[0]), float(frame_t[-1]))

    rim_mask = arrays["class_ids"] == CLASS_RIM
    rims = cluster_rims(
        arrays["boxes"][rim_mask],
        arrays["frame_t"][arrays["frame_idx"][rim_mask]],
        cuts,
        settings.shots_min_rim_dets,
    )
    result["rims"] = rims

    candidates: List[Dict[str, Any]] = []
    for rim_id, obs in _assign_ball_obs(arrays, rims, settings.shots_rim_neighborhood).items():
        rim_box = next(r["box"] for r in rims if r["rim_id"] == rim_id)
        for ep in _episodes(obs, settings.shots_gap_max_samples):
            verdict = _classify_episode(ep, rim_box, settings, result["fps_estimate"])
            t_event = float(verdict["t"])
            last_ball = _last_ball_before(ep, t_event)
            candidates.append(
                {
                    "kind": verdict["kind"],
                    "trajectory_kind": verdict["kind"],
                    "signals": ["trajectory"],
                    "t": round(t_event, 3),
                    "t_rim": round(float(verdict["t_rim"]), 3) if verdict["t_rim"] is not None else None,
                    "window": [round(ep[0].t, 3), round(ep[-1].t, 3)],
                    "segment": segment_index(t_event, cuts),
                    "rim_id": rim_id,
                    "confidence": round(float(verdict["confidence"]), 3),
                    "det_rows": [o.row for o in ep],
                    "last_ball": {
                        "t": round(last_ball.t, 3),
                        "center": [round(last_ball.cx, 2), round(last_ball.cy, 2)],
                        "det_row": last_ball.row,
                    },
                    "nearest_player_det_row": _nearest_player_row(arrays, last_ball.fidx, last_ball.cx, last_ball.cy),
                    "suppressed": False,
                    "possible_replay": False,
                }
            )

    # Fold ball_in_basket groups in as strong make evidence.
    for group in _bib_groups(arrays):
        merged = False
        for cand in candidates:
            if cand["rim_id"] is None:
                continue
            if not _windows_overlap(
                cand["window"][0], cand["window"][1], group["t_first"], group["t_last"], BIB_MERGE_PAD_SEC
            ):
                continue
            cand["signals"].append("ball_in_basket")
            if cand["kind"] == "make":
                cand["confidence"] = round(min(0.97, cand["confidence"] + 0.05), 3)
            else:
                cand["kind"] = "make"
                cand["t"] = round(group["t_best"], 3)
                cand["confidence"] = round(max(cand["confidence"], 0.8), 3)
            cand["det_rows"] = cand["det_rows"] + [int(r) for r in group["rows"]]
            cand["window"] = [
                round(min(cand["window"][0], group["t_first"]), 3),
                round(max(cand["window"][1], group["t_last"]), 3),
            ]
            merged = True
            break
        if merged:
            continue
        # Standalone bib candidate (trajectory never saw the ball).
        t_best = group["t_best"]
        rim_id = None
        if rims:
            cx, cy = group["center"]
            rim_id = min(
                rims,
                key=lambda r: float(
                    np.hypot((r["box"][0] + r["box"][2]) / 2.0 - cx, (r["box"][1] + r["box"][3]) / 2.0 - cy)
                ),
            )["rim_id"]
        fidx = int(arrays["frame_idx"][group["best_row"]])
        candidates.append(
            {
                "kind": "make",
                "trajectory_kind": None,
                "signals": ["ball_in_basket"],
                "t": round(t_best, 3),
                "t_rim": None,
                "window": [round(group["t_first"], 3), round(group["t_last"], 3)],
                "segment": segment_index(t_best, cuts),
                "rim_id": rim_id,
                "confidence": round(min(0.9, 0.6 + 0.3 * group["best_score"]), 3),
                "det_rows": [int(r) for r in group["rows"]],
                "last_ball": {
                    "t": round(t_best, 3),
                    "center": [round(group["center"][0], 2), round(group["center"][1], 2)],
                    "det_row": int(group["best_row"]),
                },
                "nearest_player_det_row": _nearest_player_row(arrays, fidx, group["center"][0], group["center"][1]),
                "suppressed": False,
                "possible_replay": False,
            }
        )

    candidates.sort(key=lambda c: c["t"])
    for candidate_id, cand in enumerate(candidates):
        cand["candidate_id"] = candidate_id

    # Replay guard 1: a window spanning a camera cut is a stitched-together
    # trajectory (live angle + replay angle) — suppress it outright.
    for cand in candidates:
        if any(cand["window"][0] < cut < cand["window"][1] for cut in cuts):
            cand["suppressed"] = True

    # Replay guard 2: the same kind of candidate repeating in a *different*
    # camera segment within a short clip smells like a replay — flag, never
    # drop (fusion drops it only when no score delta confirms it).
    active = [c for c in candidates if not c["suppressed"]]
    for j, later in enumerate(active):
        for earlier in active[:j]:
            if (
                earlier["segment"] != later["segment"]
                and earlier["kind"] == later["kind"]
                and later["t"] - earlier["t"] <= settings.shots_replay_window_sec
            ):
                later["possible_replay"] = True
                break

    result["shot_candidates"] = candidates
    return result


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``shots`` stage: camera cuts + rim tracking + make/miss candidates.

    When the detect stage was skipped (its output.json is a
    ``{"skipped": true}`` marker — no model configured), this stage writes
    its own skipped marker and no-ops; fuse treats it as absent."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    detect_out = ctx.cache.read_json("detect")  # upstream must be warm (raises otherwise)
    if isinstance(detect_out, dict) and detect_out.get("skipped"):
        logger.warning("shots: detect stage was skipped (%s) — no detections to analyze", detect_out.get("reason"))
        ctx.cache.write_json(
            ctx.stage,
            {"clip_id": ctx.clip_id, "skipped": True, "reason": "detect stage was skipped — no detections"},
        )
        return
    arrays = ctx.cache.read_arrays("detect")

    cuts = detect_cuts(ctx.clip_path, ctx.settings.base_fps, ctx.settings.shots_cut_threshold)
    if cuts:
        logger.info("shots: %d camera cut(s) at %s (clip %s)", len(cuts), cuts, ctx.clip_id)

    result = analyze(arrays, cuts, ctx.settings)
    result = {"clip_id": ctx.clip_id, **result}
    logger.info(
        "shots: %d rim(s), %d candidate(s) (clip %s)",
        len(result["rims"]),
        len(result["shot_candidates"]),
        ctx.clip_id,
    )
    ctx.cache.write_json(ctx.stage, result)
