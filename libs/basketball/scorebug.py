"""Score-bug OCR stage (Epic 2 story 1 — Signal A).

Locates the broadcast score overlay via pixel-stability analysis (no
hardcoded coordinates), discovers per-field ROIs (left/right score, team
abbreviations, game clock) by OCRing the bug region over time, reads the
fields at ~2 fps with RapidOCR, applies sliding-window majority-vote
smoothing plus basketball domain rules (scores only increase, by 1-3; the
clock decreases), and emits score-change events.

output.json schema (the fusion stage codes against this):

    {
      "clip_id": str,
      "bug_found": bool,            # false -> roi/fields null, zero reads/events
      "score_fields_found": bool,   # bug found but <2 score fields -> false, zero events
      "ocr_fps": float,             # field-read sampling rate
      "lag_sec": float,             # scorebug lag subtracted from raw times
      "roi": [x, y, w, h] | null,   # bug bounding box, full-frame pixels
      "fields": {
        "left":  {"abbr": str|null, "team": str|null, "roi": [x, y, w, h]} | null,
        "right": {"abbr": str|null, "team": str|null, "roi": [x, y, w, h]} | null,
        "clock": {"roi": [x, y, w, h]} | null
      },
      "reads": [                    # one entry per sampled frame
        {"i": int, "raw_t": float, "visible": bool,
         "left":  {"text": str, "value": int, "conf": float} | null,
         "right": {"text": str, "value": int, "conf": float} | null,
         "clock": {"text": str, "value": float, "conf": float} | null,
         "smoothed": {"left": int|null, "right": int|null}}
      ],
      "events": [
        {"raw_t": float,            # read time at which the new score was accepted
         "raw_t_start": float,      # resync events only: last read before the gap
         "t": float,                # event time = raw detection time - lag (clamped >= 0)
         "t_end": float | null,     # resync events only: window end (raw_t - lag)
         "side": "left" | "right",
         "team_abbr": str | null,   # abbreviation as read from the bug
         "team": str | null,        # alias-mapped team key or null (fusion resolves)
         "delta": int,              # score increment (> 3 only on resync catch-up)
         "score_after": [int|null, int|null],   # [left, right] after this event
         "confidence": float,
         "resync": bool}            # true when emitted across a bug-hidden gap
      ],
      "events_typed": [Event.to_dict(), ...],  # type "score_change", evidence ["scorebug"]
      "resync_count": int
    }

Domain rules: an in-vision score delta of 1-3 is an event; a delta > 3 or a
negative delta without a visibility gap re-baselines silently (OCR glitch or
graphics reset — never an event). Any positive delta across a visibility gap
(bug hidden by replays/wipes) becomes a lower-confidence window event with
``resync: true`` spanning ``[gap_start - lag, reappearance - lag]``; a jump
greater than 3 there is a catch-up marker (typed event ``points`` = null).
"""

import logging
import re
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from libs.basketball import video
from libs.basketball.timeline import EVENT_TYPE_SCORE_CHANGE, Event

logger = logging.getLogger(__name__)

# --- Sampling ---
OCR_FPS = 2.0  # per-field read rate (capped by settings.base_fps)
LOC_MAX_FRAMES = 120  # frames used for stability analysis
LOC_ANALYSIS_WIDTH = 480  # stability analysis runs at this width
MAX_READ_FRAMES = 600  # soft cap on per-field read frames

# --- Localization thresholds ---
STABLE_IQR_MAX = 14.0  # per-pixel temporal IQR below this = "static"
EDGE_MAG_THRESHOLD = 40.0  # Sobel magnitude for an "edge" pixel
EDGE_PERSISTENCE_MIN = 0.55  # edge present in > this fraction of frames
SEED_DENSITY_MIN = 0.05  # local persistent-edge density inside the bug
MARGIN_FRAC = 0.30  # bug center must sit in the outer 30% band

# --- OCR / smoothing ---
UPSCALE_DISCOVERY = 3  # full-bug upscale for field discovery
UPSCALE_FIELD = 4  # per-field upscale before recognition
PRESENCE_CORR_MIN = 0.55  # bug-visibility correlation threshold
VOTE_WINDOW = 5  # sliding majority-vote window (frames)
MAX_PLAUSIBLE_DELTA = 3  # largest single-event score increment
SCORE_MAX = 150  # scores are ints in [0, SCORE_MAX]
DISCOVERY_MAX_FRAMES = 24  # full-bug OCR frames for field discovery
MONOTONE_TOLERANCE = 0.25  # fraction of consecutive pairs allowed to violate

# abbr (normalized) -> team key. Only exact alias matches map; anything else
# keeps team null and lets fusion resolve it.
TEAM_ALIASES: Dict[str, Tuple[str, ...]] = {
    "kansas": ("KU", "KAN", "KANSAS"),
    "kansas-state": ("KSU", "KST", "K-STATE", "KSTATE"),
}

_ABBR_TO_TEAM: Dict[str, str] = {}
for _team, _names in TEAM_ALIASES.items():
    for _name in _names:
        _ABBR_TO_TEAM[_name] = _team
        _ABBR_TO_TEAM[_name.replace("-", "")] = _team

# OCR digit-lookalike fixes, applied only when parsing score fields.
_DIGIT_FIXES = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "|": "1", "Z": "2", "S": "5", "B": "8"})

_CLOCK_RE = re.compile(r"^(\d{1,2})[:.](\d{2})(?:\.(\d))?$")
_ABBR_RE = re.compile(r"^[A-Za-z][A-Za-z.\-&']{0,9}$")


# ---------------------------------------------------------------------------
# Pure parsing / mapping / smoothing logic (unit-testable, no I/O)
# ---------------------------------------------------------------------------


def normalize_abbr(text: str) -> str:
    """Uppercase and strip everything but letters, digits, and dashes."""
    return re.sub(r"[^A-Z0-9\-]", "", text.upper())


def map_abbr_to_team(abbr: Optional[str]) -> Optional[str]:
    """Alias-table lookup; None when the abbreviation is not recognized."""
    if not abbr:
        return None
    key = normalize_abbr(abbr)
    return _ABBR_TO_TEAM.get(key) or _ABBR_TO_TEAM.get(key.replace("-", ""))


def parse_score(text: str) -> Optional[int]:
    """Parse a score field read into an int in [0, SCORE_MAX], else None."""
    cleaned = re.sub(r"\s+", "", text).upper().translate(_DIGIT_FIXES).strip(".,:;")
    if not re.fullmatch(r"\d{1,3}", cleaned):
        return None
    value = int(cleaned)
    return value if 0 <= value <= SCORE_MAX else None


def parse_clock(text: str) -> Optional[float]:
    """Parse a game-clock read (M:SS / MM:SS, ':' or '.') into seconds."""
    match = _CLOCK_RE.match(re.sub(r"\s+", "", text))
    if not match:
        return None
    minutes, seconds = int(match.group(1)), int(match.group(2))
    if seconds >= 60:
        return None
    tenths = int(match.group(3)) / 10.0 if match.group(3) else 0.0
    return minutes * 60.0 + seconds + tenths


def smooth_series(
    values: Sequence[Optional[int]],
    confs: Optional[Sequence[float]] = None,
    window: int = VOTE_WINDOW,
) -> Tuple[List[Optional[int]], List[float]]:
    """Sliding-window majority vote over per-frame reads.

    ``values[i]`` is the raw read at frame i (None = missing/invalid — hidden
    frames stay None and never vote). Ties prefer the previously smoothed
    value (stability), then the raw read at i, then the smallest candidate.
    Returns (smoothed values, mean OCR confidence of the winning votes).
    """
    n = len(values)
    half = max(0, window // 2)
    out: List[Optional[int]] = [None] * n
    out_conf = [0.0] * n
    prev: Optional[int] = None
    for i in range(n):
        if values[i] is None:
            continue
        lo, hi = max(0, i - half), min(n, i + half + 1)
        counts: Dict[int, int] = {}
        for j in range(lo, hi):
            v = values[j]
            if v is not None:
                counts[v] = counts.get(v, 0) + 1
        top = max(counts.values())
        tied = [v for v, c in counts.items() if c == top]
        if prev in tied:
            winner = prev
        elif values[i] in tied:
            winner = values[i]
        else:
            winner = min(tied)
        assert winner is not None
        if confs is not None:
            votes = [confs[j] for j in range(lo, hi) if values[j] == winner]
            out_conf[i] = float(np.mean(votes)) if votes else 0.0
        else:
            out_conf[i] = 1.0
        out[i] = winner
        prev = winner
    return out, out_conf


def extract_score_events(
    times: Sequence[float],
    left: Sequence[Optional[int]],
    right: Sequence[Optional[int]],
    left_conf: Optional[Sequence[float]] = None,
    right_conf: Optional[Sequence[float]] = None,
    *,
    lag_sec: float = 0.0,
    gap_sec: float = 2.0,
    max_delta: int = MAX_PLAUSIBLE_DELTA,
) -> List[Dict[str, Any]]:
    """State machine over smoothed per-frame score reads -> raw score events.

    Domain rules: in-vision delta 1..max_delta -> event; delta > max_delta or
    negative without a gap -> silent re-baseline; any positive delta across a
    visibility gap (> gap_sec since the side's last valid read) -> window
    event with resync=True (catch-up when delta > max_delta).
    """
    n = len(times)
    lconf = list(left_conf) if left_conf is not None else [1.0] * n
    rconf = list(right_conf) if right_conf is not None else [1.0] * n
    state: Dict[str, Optional[int]] = {"left": None, "right": None}
    last_t: Dict[str, Optional[float]] = {"left": None, "right": None}
    events: List[Dict[str, Any]] = []
    for i in range(n):
        t = times[i]
        for side, series, confs in (("left", left, lconf), ("right", right, rconf)):
            v = series[i]
            if v is None:
                continue
            s = state[side]
            if s is None:
                state[side] = v
                last_t[side] = t
                continue
            prev_t = last_t[side]
            gapped = prev_t is not None and (t - prev_t) > gap_sec
            if v != s:
                delta = v - s
                conf = float(confs[i])
                if 1 <= delta <= max_delta and not gapped:
                    state[side] = v
                    events.append(
                        {
                            "raw_t": round(t, 3),
                            "t": round(max(0.0, t - lag_sec), 3),
                            "t_end": None,
                            "side": side,
                            "delta": delta,
                            "score_after": [state["left"], state["right"]],
                            "confidence": round(min(0.98, max(0.2, conf)), 3),
                            "resync": False,
                        }
                    )
                elif delta >= 1 and gapped:
                    state[side] = v
                    t0 = round(max(0.0, (prev_t if prev_t is not None else t) - lag_sec), 3)
                    t1 = round(max(t0, t - lag_sec), 3)
                    scale = 0.6 if delta <= max_delta else 0.35
                    events.append(
                        {
                            "raw_t": round(t, 3),
                            "raw_t_start": round(prev_t, 3) if prev_t is not None else None,
                            "t": t0,
                            "t_end": t1,
                            "side": side,
                            "delta": delta,
                            "score_after": [state["left"], state["right"]],
                            "confidence": round(min(0.98, max(0.15, conf * scale)), 3),
                            "resync": True,
                        }
                    )
                else:
                    # Negative delta, or an impossible jump with the bug in
                    # vision: OCR glitch or graphics reset -> re-baseline.
                    state[side] = v
            last_t[side] = t
    return events


def _mostly_monotone(vals: Sequence[int], decreasing: bool = False, tolerance: float = MONOTONE_TOLERANCE) -> bool:
    """True when at most ``tolerance`` of consecutive steps go the wrong way."""
    if len(vals) < 2:
        return True
    diffs = [b - a for a, b in zip(vals, vals[1:])]
    bad = sum(1 for d in diffs if (d > 0 if decreasing else d < 0))
    return bad <= tolerance * len(diffs)


# ---------------------------------------------------------------------------
# Score-bug localization (pixel-stability + persistent-edge analysis)
# ---------------------------------------------------------------------------


def _locate_bug(clip_path, duration_sec: Optional[float]) -> Optional[Dict[str, Any]]:
    """Find the static overlay region. Returns None when no bug is found.

    Static overlays have (a) low per-pixel temporal IQR (robust to <25% of
    frames hiding the bug) and (b) edges that persist across frames (text and
    chrome), and (c) sit in the frame margins. No coordinates are assumed.
    """
    loc_fps = 2.0
    if duration_sec and duration_sec > 0:
        loc_fps = min(2.0, max(0.5, LOC_MAX_FRAMES / duration_sec))
    grays: List[np.ndarray] = []
    frame_size: Optional[Tuple[int, int]] = None  # (W, H) full-res
    scale = 1.0
    for _t, frame in video.sample_frames(clip_path, loc_fps):
        if frame_size is None:
            h, w = frame.shape[:2]
            frame_size = (w, h)
            scale = min(1.0, LOC_ANALYSIS_WIDTH / w)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if scale < 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        grays.append(gray)
        if len(grays) >= LOC_MAX_FRAMES:
            break
    if frame_size is None or len(grays) < 4:
        logger.info("scorebug: too few frames (%d) for stability analysis", len(grays))
        return None

    stack = np.stack(grays).astype(np.float32)
    q25 = np.percentile(stack, 25, axis=0)
    q75 = np.percentile(stack, 75, axis=0)
    stable = (q75 - q25) < STABLE_IQR_MAX

    edge_votes = np.zeros(stack.shape[1:], dtype=np.float32)
    for gray in grays:
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edge_votes += (cv2.magnitude(gx, gy) > EDGE_MAG_THRESHOLD).astype(np.float32)
    edge_persist = edge_votes / len(grays)

    seed = (stable & (edge_persist > EDGE_PERSISTENCE_MIN)).astype(np.uint8)
    density = cv2.blur(seed.astype(np.float32), (31, 11))
    mask = ((density > SEED_DENSITY_MIN) & stable).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((13, 41), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 7), np.uint8))

    num, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    h_small, w_small = mask.shape
    best: Optional[Tuple[float, Tuple[int, int, int, int]]] = None
    for k in range(1, num):
        x, y, bw, bh, _area = (int(v) for v in stats[k])
        if bw < 0.05 * w_small or bh < 0.015 * h_small:
            continue
        if bw * bh > 0.5 * w_small * h_small:
            continue  # near-fullscreen static region: static camera, not a bug
        cx, cy = centroids[k]
        in_margin = (
            cx < MARGIN_FRAC * w_small
            or cx > (1 - MARGIN_FRAC) * w_small
            or cy < MARGIN_FRAC * h_small
            or cy > (1 - MARGIN_FRAC) * h_small
        )
        if not in_margin:
            continue
        score = float(seed[y : y + bh, x : x + bw].sum())
        if best is None or score > best[0]:
            best = (score, (x, y, bw, bh))
    if best is None:
        logger.info("scorebug: no stable margin overlay region found")
        return None

    x, y, bw, bh = best[1]
    pad_x, pad_y = int(round(0.5 * bh)), int(round(0.3 * bh))
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(w_small, x + bw + pad_x)
    y1 = min(h_small, y + bh + pad_y)

    ref = np.median(stack[:, y0:y1, x0:x1], axis=0).astype(np.float32)
    stable_crop = stable[y0:y1, x0:x1]

    full_w, full_h = frame_size
    fx0 = max(0, int(round(x0 / scale)))
    fy0 = max(0, int(round(y0 / scale)))
    fx1 = min(full_w, int(round(x1 / scale)))
    fy1 = min(full_h, int(round(y1 / scale)))
    if fx1 - fx0 < 8 or fy1 - fy0 < 4:
        return None
    return {
        "roi": (fx0, fy0, fx1 - fx0, fy1 - fy0),
        "ref": ref,
        "stable": stable_crop,
        "frame_size": frame_size,
    }


def _bug_presence(crop_bgr: np.ndarray, loc: Dict[str, Any]) -> float:
    """Correlation of a bug crop against the stable reference (1.0 = visible)."""
    ref: np.ndarray = loc["ref"]
    mask: np.ndarray = loc["stable"]
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (ref.shape[1], ref.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32)
    if int(mask.sum()) >= 50:
        a, b = gray[mask], ref[mask]
    else:
        a, b = gray.ravel(), ref.ravel()
    if float(a.std()) < 1.0 or float(b.std()) < 1.0:
        return 1.0 if abs(float(a.mean() - b.mean())) < 12.0 else 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _sample_bug_crops(clip_path, loc: Dict[str, Any], ocr_fps: float) -> List[Tuple[float, np.ndarray, bool]]:
    """Second decode pass: (t, bug crop, visible) at the OCR sampling rate."""
    x, y, w, h = loc["roi"]
    crops: List[Tuple[float, np.ndarray, bool]] = []
    for t, frame in video.sample_frames(clip_path, ocr_fps):
        crop = frame[y : y + h, x : x + w].copy()
        visible = _bug_presence(crop, loc) >= PRESENCE_CORR_MIN
        crops.append((t, crop, visible))
        if len(crops) >= MAX_READ_FRAMES:
            break
    return crops


# ---------------------------------------------------------------------------
# Field discovery (full-bug OCR over time -> per-field ROIs)
# ---------------------------------------------------------------------------


def _cluster_tokens(all_tokens: List[Dict[str, Any]], n_frames: int) -> List[Dict[str, Any]]:
    """Group per-frame OCR tokens into spatially stable clusters."""
    if not all_tokens:
        return []
    med_h = median(tok["y1"] - tok["y0"] for tok in all_tokens)
    tol = max(10.0, 0.8 * med_h)
    clusters: List[Dict[str, Any]] = []
    for tok in all_tokens:
        target = None
        for cluster in clusters:
            if abs(tok["cx"] - cluster["cx"]) < tol and abs(tok["cy"] - cluster["cy"]) < tol:
                target = cluster
                break
        if target is None:
            target = {
                "cx": tok["cx"],
                "cy": tok["cy"],
                "x0": tok["x0"],
                "x1": tok["x1"],
                "y0": tok["y0"],
                "y1": tok["y1"],
                "items": [],
            }
            clusters.append(target)
        n = len(target["items"])
        target["cx"] = (target["cx"] * n + tok["cx"]) / (n + 1)
        target["cy"] = (target["cy"] * n + tok["cy"]) / (n + 1)
        target["x0"] = min(target["x0"], tok["x0"])
        target["x1"] = max(target["x1"], tok["x1"])
        target["y0"] = min(target["y0"], tok["y0"])
        target["y1"] = max(target["y1"], tok["y1"])
        target["items"].append(tok)
    min_support = max(3, int(0.25 * n_frames))
    kept = [c for c in clusters if len(c["items"]) >= min_support]
    for cluster in kept:
        cluster["h"] = cluster["y1"] - cluster["y0"]
    return kept


def _classify_clusters(clusters: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Split clusters into (score candidates, clock candidates, abbr candidates)."""
    scores: List[Dict[str, Any]] = []
    clocks: List[Dict[str, Any]] = []
    abbrs: List[Dict[str, Any]] = []
    for cluster in clusters:
        texts = [item["text"] for item in cluster["items"]]
        n = len(texts)
        clock_vals = [v for v in (parse_clock(t) for t in texts) if v is not None]
        if len(clock_vals) >= 0.5 * n:
            cluster["net"] = clock_vals[-1] - clock_vals[0] if len(clock_vals) >= 2 else 0.0
            if _mostly_monotone([int(v * 10) for v in clock_vals], decreasing=True):
                clocks.append(cluster)
                continue
        score_vals = [v for v in (parse_score(t) for t in texts) if v is not None]
        if len(score_vals) >= 0.6 * n and score_vals:
            net = score_vals[-1] - score_vals[0]
            if net < 0 and _mostly_monotone(score_vals, decreasing=True):
                continue  # counting down: shot clock / countdown graphic
            if _mostly_monotone(score_vals, decreasing=False):
                cluster["net"] = net
                cluster["values"] = score_vals
                scores.append(cluster)
                continue
        alpha = [t for t in texts if _ABBR_RE.match(t.strip())]
        if len(alpha) >= 0.6 * n and alpha:
            normalized = [normalize_abbr(t) for t in alpha if normalize_abbr(t)]
            if not normalized:
                continue
            mode = max(set(normalized), key=normalized.count)
            if normalized.count(mode) >= 0.5 * len(normalized):
                cluster["abbr"] = mode
                abbrs.append(cluster)
    return scores, clocks, abbrs


def _pick_score_pair(cands: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Choose the two score fields; changing clusters and big digits win."""
    if len(cands) < 2:
        return None

    def rank(c: Dict[str, Any]) -> Tuple[int, int, float]:
        return (1 if c["net"] > 0 else 0, len(c["items"]), c["h"])

    ordered = sorted(cands, key=rank, reverse=True)
    first = ordered[0]
    rest = ordered[1:]
    similar = [c for c in rest if max(c["h"], first["h"]) / max(1e-3, min(c["h"], first["h"])) <= 1.7]
    partner = max(similar or rest, key=rank)
    a, b = sorted([first, partner], key=lambda c: (c["cx"], c["cy"]))
    return a, b


def _cluster_roi(cluster: Dict[str, Any], crop_shape: Tuple[int, ...]) -> Tuple[int, int, int, int]:
    """Cluster bbox (bug-crop coords) padded for digit growth, clamped."""
    height = max(4.0, cluster["h"])
    pad_x, pad_y = 0.7 * height, 0.35 * height
    ch, cw = crop_shape[:2]
    x0 = int(max(0, cluster["x0"] - pad_x))
    y0 = int(max(0, cluster["y0"] - pad_y))
    x1 = int(min(cw, cluster["x1"] + pad_x))
    y1 = int(min(ch, cluster["y1"] + pad_y))
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def _discover_fields(
    crops: List[Tuple[float, np.ndarray, bool]], ocr: Any
) -> Optional[Dict[str, Optional[Dict[str, Any]]]]:
    """OCR the whole bug over time; identify score/clock/abbr field ROIs."""
    visible = [(t, crop) for t, crop, vis in crops if vis]
    if len(visible) < 3:
        return None
    step = max(1, len(visible) // DISCOVERY_MAX_FRAMES)
    chosen = visible[::step][:DISCOVERY_MAX_FRAMES]
    crop_shape = chosen[0][1].shape

    all_tokens: List[Dict[str, Any]] = []
    for _t, crop in chosen:
        up = cv2.resize(crop, None, fx=UPSCALE_DISCOVERY, fy=UPSCALE_DISCOVERY, interpolation=cv2.INTER_CUBIC)
        result, _elapse = ocr(up)
        for box, text, conf in result or []:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            all_tokens.append(
                {
                    "text": str(text).strip(),
                    "conf": float(conf),
                    "cx": float(np.mean(xs)) / UPSCALE_DISCOVERY,
                    "cy": float(np.mean(ys)) / UPSCALE_DISCOVERY,
                    "x0": float(min(xs)) / UPSCALE_DISCOVERY,
                    "x1": float(max(xs)) / UPSCALE_DISCOVERY,
                    "y0": float(min(ys)) / UPSCALE_DISCOVERY,
                    "y1": float(max(ys)) / UPSCALE_DISCOVERY,
                }
            )
    clusters = _cluster_tokens(all_tokens, len(chosen))
    if not clusters:
        return None
    score_cands, clock_cands, abbr_cands = _classify_clusters(clusters)
    pair = _pick_score_pair(score_cands)
    if pair is None:
        logger.info(
            "scorebug: found %d score-like clusters — need 2 (clock=%d, abbr=%d)",
            len(score_cands),
            len(clock_cands),
            len(abbr_cands),
        )
        return None
    left_cluster, right_cluster = pair

    # Assign the nearest stable alphabetic token to each score field (unique).
    assignments: Dict[str, Optional[str]] = {"left": None, "right": None}
    candidates = []
    for side, sc in (("left", left_cluster), ("right", right_cluster)):
        for ab in abbr_cands:
            dist = float(np.hypot(ab["cx"] - sc["cx"], ab["cy"] - sc["cy"]))
            candidates.append((dist, side, id(ab), ab))
    used_ids = set()
    for dist, side, ab_id, ab in sorted(candidates, key=lambda item: item[0]):
        if assignments[side] is None and ab_id not in used_ids:
            assignments[side] = ab["abbr"]
            used_ids.add(ab_id)

    clock_cluster = max(clock_cands, key=lambda c: (c.get("net", 0) < 0, len(c["items"])), default=None)

    fields: Dict[str, Optional[Dict[str, Any]]] = {
        "left": {
            "abbr": assignments["left"],
            "team": map_abbr_to_team(assignments["left"]),
            "roi_crop": _cluster_roi(left_cluster, crop_shape),
        },
        "right": {
            "abbr": assignments["right"],
            "team": map_abbr_to_team(assignments["right"]),
            "roi_crop": _cluster_roi(right_cluster, crop_shape),
        },
        "clock": {"roi_crop": _cluster_roi(clock_cluster, crop_shape)} if clock_cluster else None,
    }
    return fields


# ---------------------------------------------------------------------------
# Per-field reading
# ---------------------------------------------------------------------------


def _ocr_field(field_crop: np.ndarray, ocr: Any, kind: str) -> Optional[Dict[str, Any]]:
    """crop -> upscale INTER_CUBIC -> grayscale/threshold variants -> RapidOCR."""
    up = cv2.resize(field_crop, None, fx=UPSCALE_FIELD, fy=UPSCALE_FIELD, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    _thr, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants = (gray, otsu, 255 - otsu)
    best: Optional[Dict[str, Any]] = None
    for variant in variants:
        result, _elapse = ocr(cv2.cvtColor(variant, cv2.COLOR_GRAY2BGR), use_det=False, use_cls=False)
        if not result:
            continue
        text, conf = str(result[0][0]).strip(), float(result[0][1])
        value = parse_score(text) if kind == "score" else parse_clock(text)
        if value is None:
            continue
        if best is None or conf > best["conf"]:
            best = {"text": text, "value": value, "conf": round(conf, 3)}
        if conf >= 0.85:
            break
    return best


def _crop_field(bug_crop: np.ndarray, roi_crop: Tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = roi_crop
    return bug_crop[y : y + h, x : x + w]


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------


def _empty_output(clip_id: str, ocr_fps: float, lag_sec: float, **overrides: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "clip_id": clip_id,
        "bug_found": False,
        "score_fields_found": False,
        "ocr_fps": ocr_fps,
        "lag_sec": lag_sec,
        "roi": None,
        "fields": {"left": None, "right": None, "clock": None},
        "reads": [],
        "events": [],
        "events_typed": [],
        "resync_count": 0,
    }
    out.update(overrides)
    return out


def _typed_event(event: Dict[str, Any]) -> Event:
    conf: Dict[str, float] = {"overall": event["confidence"]}
    plausible = 1 <= event["delta"] <= MAX_PLAUSIBLE_DELTA
    if plausible:
        conf["points"] = event["confidence"]
    if event["team"]:
        conf["team"] = event["confidence"]
    return Event(
        t=event["t"],
        t_end=event["t_end"],
        type=EVENT_TYPE_SCORE_CHANGE,
        team=event["team"],
        points=event["delta"] if plausible else None,
        confidence=conf,
        evidence=["scorebug"],
    )


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``scorebug`` stage: locate the bug, read fields, emit score events."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    lag_sec = float(ctx.settings.scorebug_lag_sec)
    base_fps = float(ctx.settings.base_fps)
    ocr_fps = min(OCR_FPS, base_fps) if base_fps > 0 else OCR_FPS

    duration = None
    try:
        decode_info = ctx.cache.read_json("decode")
        duration = (decode_info.get("probe") or {}).get("duration_sec")
    except FileNotFoundError:
        try:
            duration = video.probe(ctx.clip_path).get("duration_sec")
        except Exception:  # noqa: BLE001 — probe is advisory; sampling still works
            duration = None

    loc = _locate_bug(ctx.clip_path, duration)
    if loc is None:
        logger.info("scorebug: no bug found for clip %s", ctx.clip_id)
        ctx.cache.write_json(ctx.stage, _empty_output(ctx.clip_id, ocr_fps, lag_sec))
        return

    roi = [int(v) for v in loc["roi"]]
    crops = _sample_bug_crops(ctx.clip_path, loc, ocr_fps)

    from rapidocr_onnxruntime import RapidOCR  # lazy: heavy import, stage-only

    ocr = RapidOCR()
    fields = _discover_fields(crops, ocr)
    if fields is None or fields["left"] is None or fields["right"] is None:
        logger.info("scorebug: bug at %s but no score fields discovered", roi)
        ctx.cache.write_json(ctx.stage, _empty_output(ctx.clip_id, ocr_fps, lag_sec, bug_found=True, roi=roi))
        return

    def full_roi(field: Optional[Dict[str, Any]]) -> Optional[List[int]]:
        if field is None:
            return None
        x, y, w, h = field["roi_crop"]
        return [roi[0] + x, roi[1] + y, w, h]

    times: List[float] = []
    raw_vals: Dict[str, List[Optional[int]]] = {"left": [], "right": []}
    raw_confs: Dict[str, List[float]] = {"left": [], "right": []}
    reads: List[Dict[str, Any]] = []
    for i, (t, crop, vis) in enumerate(crops):
        entry: Dict[str, Any] = {
            "i": i,
            "raw_t": round(t, 3),
            "visible": vis,
            "left": None,
            "right": None,
            "clock": None,
        }
        for side in ("left", "right"):
            value: Optional[int] = None
            conf = 0.0
            if vis:
                field = fields[side]
                assert field is not None
                read = _ocr_field(_crop_field(crop, field["roi_crop"]), ocr, "score")
                if read is not None:
                    entry[side] = read
                    value, conf = int(read["value"]), float(read["conf"])
            raw_vals[side].append(value)
            raw_confs[side].append(conf)
        if vis and fields["clock"] is not None:
            entry["clock"] = _ocr_field(_crop_field(crop, fields["clock"]["roi_crop"]), ocr, "clock")
        times.append(t)
        reads.append(entry)

    left_sm, left_sm_conf = smooth_series(raw_vals["left"], raw_confs["left"])
    right_sm, right_sm_conf = smooth_series(raw_vals["right"], raw_confs["right"])
    for i, entry in enumerate(reads):
        entry["smoothed"] = {"left": left_sm[i], "right": right_sm[i]}

    gap_sec = max(2.0, 3.0 / ocr_fps)
    events = extract_score_events(
        times, left_sm, right_sm, left_sm_conf, right_sm_conf, lag_sec=lag_sec, gap_sec=gap_sec
    )
    for event in events:
        side_field = fields[event["side"]]
        assert side_field is not None
        event["team_abbr"] = side_field["abbr"]
        event["team"] = side_field["team"]

    # Debug artifact: first visible bug crop (written before output.json — the
    # warm marker must be the last write).
    first_visible = next((crop for _t, crop, vis in crops if vis), None)
    if first_visible is not None:
        cv2.imwrite(str(ctx.cache.path(ctx.stage, "bug.png")), first_visible)

    output = {
        "clip_id": ctx.clip_id,
        "bug_found": True,
        "score_fields_found": True,
        "ocr_fps": ocr_fps,
        "lag_sec": lag_sec,
        "roi": roi,
        "fields": {
            "left": {"abbr": fields["left"]["abbr"], "team": fields["left"]["team"], "roi": full_roi(fields["left"])},
            "right": {
                "abbr": fields["right"]["abbr"],
                "team": fields["right"]["team"],
                "roi": full_roi(fields["right"]),
            },
            "clock": {"roi": full_roi(fields["clock"])} if fields["clock"] else None,
        },
        "reads": reads,
        "events": events,
        "events_typed": [_typed_event(e).to_dict() for e in events],
        "resync_count": sum(1 for e in events if e["resync"]),
    }
    ctx.cache.write_json(ctx.stage, output)
    logger.info(
        "scorebug: clip %s -> %d event(s), %d read frame(s), roi=%s",
        ctx.clip_id,
        len(events),
        len(reads),
        roi,
    )
