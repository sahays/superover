"""Jersey-number recognition stage (Epic 3 story 2 — Signal C, part 2).

Associates ``number``-class detections to player tracks (box-center
containment), gates crops for legibility (min pixel height + Laplacian-
variance sharpness), reads digits with RapidOCR in recognition-only mode on
4x-upscaled gray/Otsu variants, and aggregates per track with a conservative
vote: a jersey is accepted only with >= ``jersey_min_reads`` reads for the
winner AND a vote margin >= ``jersey_vote_margin`` over the runner-up.
Single- vs double-digit reads ("4" vs "44") are distinct votes — never
merged. Below threshold the track's jersey is ``null``: the acceptance
criterion is *never confidently wrong* — prefer null.

Upstream inputs (read via the clip cache):

* ``detect`` ``arrays.npz`` — flat detection arrays aligned on axis 0
  (boxes/scores/class_ids/frame_idx + frame_t); canonical class ids
  player=3, number=4 (see libs/basketball/detect.py).
* ``teams`` ``output.json`` — ``{clip_id, n_tracks, tracks: [{track_id,
  cluster, cluster_confidence, det_rows, t_start, t_end}], cluster_stats,
  cuts}`` where ``det_rows`` are ascending indices into the detect npz.
  When absent (teams stage not run), every player detection row becomes its
  own single-frame pseudo-track (``track_id`` = detect npz row index); with
  default thresholds those can never accumulate >= 3 reads, so jerseys stay
  null — the fallback exists so the stage degrades instead of failing. In
  pseudo-track mode only tracks with at least one associated number
  detection are emitted, and track ids do NOT share a space with teams'.

output.json schema (the fusion stage codes against this)::

    {
      "clip_id": str,
      "tracks": [
        {
          "track_id": int,          # teams track_id (or detect row in fallback)
          "jersey": str | null,     # canonical number string, e.g. "4", "23"
          "confidence": float,      # 0.0 when jersey is null
          "n_reads": int,           # accepted OCR reads for this track
          "votes": {"<num>": count} # e.g. {"23": 5, "28": 1}
        },
        ...
      ],
      "unassociated_numbers": int   # number dets inside no tracked player box
    }

Frames are re-decoded on demand via ``sample_frames(clip, base_fps)`` — the
exact frame sequence the detect stage indexed; alignment against detect's
``frame_t`` is verified and any mismatch raises.
"""

import logging
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from libs.basketball.video import sample_frames

logger = logging.getLogger(__name__)

# Canonical detect-stage class ids (fixed contract, libs/basketball/detect.py).
PLAYER_CLASS_ID = 3
NUMBER_CLASS_ID = 4

UPSCALE = 4.0  # legible crops are upscaled 4x (INTER_CUBIC) before OCR
MIN_READ_CONF = 0.4  # discard OCR reads below this recognition confidence
EARLY_STOP_CONF = 0.85  # stop trying preprocessing variants at this confidence
MIN_CROP_WIDTH_PX = 3  # degenerate-width floor (a "1" at 12 px is ~3-4 px wide)

# OCR digit-lookalike fixes for jersey reads.
# TODO(consolidate): scorebug.py keeps a near-identical table (_DIGIT_FIXES);
# unify into a shared helper once both stages have settled.
_DIGIT_LOOKALIKES = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "S": "5",
        "s": "5",
        "B": "8",
        "b": "8",
        "I": "1",
        "i": "1",
        "L": "1",
        "l": "1",
        "|": "1",
    }
)


# ---------------------------------------------------------------------------
# Crop association
# ---------------------------------------------------------------------------


def associate_number(number_box: Sequence[float], candidate_boxes: Sequence[Sequence[float]]) -> Optional[int]:
    """Index of the smallest candidate box containing the number box center.

    Boxes are xyxy. Ties on containment resolve to the smallest box (the
    nearest enclosing player); returns None when no candidate contains the
    center.
    """
    cx = (float(number_box[0]) + float(number_box[2])) / 2.0
    cy = (float(number_box[1]) + float(number_box[3])) / 2.0
    best: Optional[int] = None
    best_area = math.inf
    for i, box in enumerate(candidate_boxes):
        x1, y1, x2, y2 = (float(v) for v in box)
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
            if area < best_area:
                best, best_area = i, area
    return best


# ---------------------------------------------------------------------------
# Legibility gate
# ---------------------------------------------------------------------------


def sharpness(crop_bgr: np.ndarray) -> float:
    """Laplacian variance of the grayscale crop (higher = sharper)."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def is_legible(crop_bgr: np.ndarray, min_px: int, min_sharpness: float) -> bool:
    """True when the crop is big and sharp enough to be worth OCRing."""
    if crop_bgr is None or crop_bgr.size == 0:
        return False
    h, w = crop_bgr.shape[:2]
    if h < min_px or w < MIN_CROP_WIDTH_PX:
        return False
    return sharpness(crop_bgr) >= min_sharpness


# ---------------------------------------------------------------------------
# Digit reading
# ---------------------------------------------------------------------------


def normalize_jersey_text(text: Any) -> Optional[str]:
    """OCR text -> canonical jersey number string ("0".."99"), or None.

    Strips all whitespace, applies digit-lookalike fixes (O->0, S->5, B->8,
    I/L->1), then accepts only 1-2 ASCII digits. The result is canonicalized
    through int(), so "07" -> "7" (limitation: "00" collapses to "0").
    """
    cleaned = "".join(str(text).split()).translate(_DIGIT_LOOKALIKES)
    if not (1 <= len(cleaned) <= 2) or not cleaned.isascii() or not cleaned.isdigit():
        return None
    return str(int(cleaned))


def read_number(crop_bgr: np.ndarray, ocr: Any) -> Optional[Tuple[str, float]]:
    """One legible crop -> (jersey string, OCR confidence), or None.

    Upscales 4x INTER_CUBIC, then tries gray / Otsu / inverted-Otsu variants
    through RapidOCR recognition-only; keeps the highest-confidence variant
    whose text normalizes to a valid 0-99 number.
    """
    up = cv2.resize(crop_bgr, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    _thr, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    best: Optional[Tuple[str, float]] = None
    for variant in (gray, otsu, 255 - otsu):
        result, _elapse = ocr(cv2.cvtColor(variant, cv2.COLOR_GRAY2BGR), use_det=False, use_cls=False)
        if not result:
            continue
        text, conf = str(result[0][0]), float(result[0][1])
        number = normalize_jersey_text(text)
        if number is None or conf < MIN_READ_CONF:
            continue
        if best is None or conf > best[1]:
            best = (number, conf)
        if conf >= EARLY_STOP_CONF:
            break
    return best


# ---------------------------------------------------------------------------
# Tracklet vote
# ---------------------------------------------------------------------------


def vote_jersey(votes: Counter, min_reads: int, vote_margin: int) -> Tuple[Optional[str], float]:
    """Counter of number-string votes -> (jersey or None, confidence).

    Accept only when the winner has >= ``min_reads`` votes AND leads the
    runner-up by >= ``vote_margin``. "4" and "44" are distinct keys — no
    merging. Confidence grows with both the margin fraction and the read
    count; it is 0.0 whenever the jersey is null (never confidently wrong).
    """
    if not votes:
        return None, 0.0
    ranked = votes.most_common()
    winner, top = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    if top < min_reads or (top - runner_up) < vote_margin:
        return None, 0.0
    total = sum(votes.values())
    margin_frac = (top - runner_up) / total
    count_factor = min(1.0, top / (2.0 * max(min_reads, 1)))
    return winner, round(margin_frac * count_factor, 3)


# ---------------------------------------------------------------------------
# Roster mapping (pure helper — CLI wiring is owned elsewhere)
# ---------------------------------------------------------------------------


def apply_roster(tracks: List[Dict[str, Any]], roster: Dict[Any, Any]) -> List[Dict[str, Any]]:
    """Add ``player_name`` to each track dict from a jersey -> name roster.

    Pure: returns new dicts, never mutates the input. Roster keys are
    normalized to canonical number strings ("07" and 7 both match jersey
    "7"); tracks with a null or unmapped jersey get ``player_name: None``.
    """
    normalized: Dict[str, Any] = {}
    for key, name in (roster or {}).items():
        text = str(key).strip()
        if text.isascii() and text.isdigit():
            text = str(int(text))
        normalized[text] = name
    result = []
    for track in tracks:
        entry = dict(track)
        jersey = entry.get("jersey")
        entry["player_name"] = normalized.get(jersey) if jersey is not None else None
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------


def _load_tracks(ctx) -> Tuple[List[Dict[str, Any]], bool]:
    """teams tracks, or single-detection pseudo-tracks when teams never ran."""
    try:
        teams_out = ctx.cache.read_json("teams")
    except FileNotFoundError:
        logger.info("jersey: no teams output for clip %s — falling back to per-detection pseudo-tracks", ctx.clip_id)
        return [], True
    return list(teams_out["tracks"]), False


def _crop_box(frame: np.ndarray, box: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    x1 = max(0, int(math.floor(float(box[0]))))
    y1 = max(0, int(math.floor(float(box[1]))))
    x2 = min(w, int(math.ceil(float(box[2]))))
    y2 = min(h, int(math.ceil(float(box[3]))))
    return frame[y1:y2, x1:x2]


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``jersey`` stage: number crops -> OCR reads -> per-track vote.

    When the detect stage was skipped (its output.json is a
    ``{"skipped": true}`` marker — no model configured), this stage writes
    its own skipped marker and no-ops; fuse treats it as absent."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    try:
        detect_out = ctx.cache.read_json("detect")
    except FileNotFoundError:
        detect_out = {}
    if isinstance(detect_out, dict) and detect_out.get("skipped"):
        logger.warning("jersey: detect stage was skipped (%s) — no number crops to read", detect_out.get("reason"))
        ctx.cache.write_json(
            ctx.stage,
            {"clip_id": ctx.clip_id, "skipped": True, "reason": "detect stage was skipped — no detections"},
        )
        return

    arrays = ctx.cache.read_arrays("detect")
    boxes = arrays["boxes"]
    class_ids = arrays["class_ids"]
    frame_idx = arrays["frame_idx"]
    frame_t = arrays["frame_t"]

    tracks, pseudo = _load_tracks(ctx)
    if pseudo:
        player_rows = np.nonzero(class_ids == PLAYER_CLASS_ID)[0]
        tracks = [{"track_id": int(row), "det_rows": [int(row)]} for row in player_rows]

    # det row -> track_id, restricted to player-class rows.
    row_to_track: Dict[int, Any] = {}
    for track in tracks:
        for row in track["det_rows"]:
            if class_ids[row] == PLAYER_CLASS_ID:
                row_to_track[int(row)] = track["track_id"]

    # Associate every number detection with the containing tracked player box.
    number_rows = np.nonzero(class_ids == NUMBER_CLASS_ID)[0]
    tracked_players_by_frame: Dict[int, List[int]] = defaultdict(list)
    for row in row_to_track:
        tracked_players_by_frame[int(frame_idx[row])].append(row)

    unassociated = 0
    to_read_by_frame: Dict[int, List[Tuple[int, Any]]] = defaultdict(list)  # frame -> [(number row, track_id)]
    for row in number_rows:
        frame = int(frame_idx[row])
        candidates = tracked_players_by_frame.get(frame, [])
        hit = associate_number(boxes[row], [boxes[r] for r in candidates])
        if hit is None:
            unassociated += 1
            continue
        to_read_by_frame[frame].append((int(row), row_to_track[candidates[hit]]))

    # Decode only the frames that carry associated number crops; the sampling
    # is identical to the detect stage's, and alignment is verified via PTS.
    votes_by_track: Dict[Any, Counter] = defaultdict(Counter)
    if to_read_by_frame:
        from rapidocr_onnxruntime import RapidOCR  # lazy: heavy import, stage-only

        ocr = RapidOCR()
        pending = set(to_read_by_frame)
        last_needed = max(pending)
        for k, (t, frame) in enumerate(sample_frames(ctx.clip_path, ctx.settings.base_fps)):
            if k >= frame_t.shape[0] or abs(t - float(frame_t[k])) > 1e-6:
                raise RuntimeError(
                    f"jersey: frame sampling misaligned with detect cache at frame {k} "
                    f"(t={t:.6f}); was base_fps changed since detect ran? Re-run detect."
                )
            for row, track_id in to_read_by_frame.get(k, ()):
                crop = _crop_box(frame, boxes[row])
                if not is_legible(crop, ctx.settings.jersey_min_crop_px, ctx.settings.jersey_min_sharpness):
                    continue
                read = read_number(crop, ocr)
                if read is not None:
                    votes_by_track[track_id][read[0]] += 1
            pending.discard(k)
            if k >= last_needed:
                break
        if pending:
            raise RuntimeError(
                f"jersey: clip yielded fewer sampled frames than the detect cache indexed "
                f"(missing frames {sorted(pending)}); re-run detect against this clip."
            )

    # Emit one entry per track. In pseudo-track mode only tracks that had an
    # associated number detection carry information; skip the rest.
    associated_tracks = {track_id for reads in to_read_by_frame.values() for _row, track_id in reads}
    track_entries = []
    for track in tracks:
        track_id = track["track_id"]
        if pseudo and track_id not in associated_tracks:
            continue
        votes = votes_by_track.get(track_id, Counter())
        jersey, confidence = vote_jersey(votes, ctx.settings.jersey_min_reads, ctx.settings.jersey_vote_margin)
        track_entries.append(
            {
                "track_id": track_id,
                "jersey": jersey,
                "confidence": confidence,
                "n_reads": int(sum(votes.values())),
                "votes": dict(votes.most_common()),
            }
        )

    ctx.cache.write_json(
        ctx.stage,
        {
            "clip_id": ctx.clip_id,
            "tracks": track_entries,
            "unassociated_numbers": unassociated,
        },
    )
