"""Typed event model + JSON I/O + signal fusion for the basketball timeline.

Two layers live here:

* **Event model + (de)serialization** (Epic 1) — the ``Event`` dataclass and
  the predictions file format below, which is what the CLI emits and
  ``evals/basketball/run_eval.py`` consumes.
* **Signal fusion** (Epic 2 story 3) — the ``fuse`` pipeline stage
  (``run_stage`` / ``fuse_signals``) combining Signal A (score-bug OCR) and
  Signal B (trajectory + ball_in_basket) plus the teams/jersey attribution
  stages into final scoring events. See ``fuse_signals`` for the full
  fusion truth table. Shot typing (Epic 4 story 1) also lives here:
  delta arithmetic (``_delta_type``), the and-one matching guard
  (``_match_deltas``), and free-throw scene corroboration
  (``ft_scene_corroborated``).

Predictions file format::

    {"clip_id": "<clip id>", "events": [<Event.to_dict()>, ...]}

Event fields (per the HLD in docs/plans/basketball-video-analysis/plan.md):
``t`` (sec), optional ``t_end``, ``type`` ("shot" | "free_throw" |
"score_change" | ...), ``outcome`` ("made" | "missed" | None), ``team``,
``points``, ``jersey``, per-attribute ``confidence`` dict (plus "overall"),
and an ``evidence`` list naming the signals that contributed.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Event types with scoring semantics (used by the eval harness).
EVENT_TYPE_SHOT = "shot"
EVENT_TYPE_FREE_THROW = "free_throw"
EVENT_TYPE_SCORE_CHANGE = "score_change"
SCORING_EVENT_TYPES = frozenset({EVENT_TYPE_SHOT, EVENT_TYPE_FREE_THROW})

OUTCOME_MADE = "made"
OUTCOME_MISSED = "missed"


@dataclass
class Event:
    """One timeline event. Timestamps are seconds from clip start (PTS)."""

    t: float
    type: str  # "shot" | "free_throw" | "score_change" | ...
    t_end: Optional[float] = None
    outcome: Optional[str] = None  # "made" | "missed" | None
    team: Optional[str] = None
    points: Optional[int] = None
    jersey: Optional[str] = None
    confidence: Dict[str, float] = field(default_factory=dict)  # per-attribute + "overall"
    evidence: List[str] = field(default_factory=list)

    @property
    def midpoint(self) -> float:
        """Event reference time: midpoint of [t, t_end] when t_end is set."""
        if self.t_end is not None:
            return (self.t + self.t_end) / 2.0
        return self.t

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        known = {f for f in cls.__dataclass_fields__}
        extra = set(data) - known
        if extra:
            raise ValueError(f"Unknown Event fields: {sorted(extra)}")
        if "t" not in data or "type" not in data:
            raise ValueError("Event requires at least 't' and 'type'")
        event = cls(**data)
        if event.jersey is not None:
            event.jersey = str(event.jersey)
        return event

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Event":
        return cls.from_dict(json.loads(text))


def events_to_json(events: List[Event]) -> str:
    return json.dumps([e.to_dict() for e in events], indent=2)


def events_from_json(text: str) -> List[Event]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of events")
    return [Event.from_dict(item) for item in data]


# --- Predictions file: {clip_id, events: [...]} ---


def predictions_to_dict(clip_id: str, events: List[Event]) -> Dict[str, Any]:
    return {"clip_id": clip_id, "events": [e.to_dict() for e in events]}


def predictions_from_dict(data: Dict[str, Any]) -> Tuple[str, List[Event]]:
    if "clip_id" not in data or "events" not in data:
        raise ValueError("Predictions file requires 'clip_id' and 'events'")
    events = [Event.from_dict(item) for item in data["events"]]
    return str(data["clip_id"]), events


def write_predictions(path: Union[str, Path], clip_id: str, events: List[Event]) -> None:
    Path(path).write_text(json.dumps(predictions_to_dict(clip_id, events), indent=2) + "\n", encoding="utf-8")


def read_predictions(path: Union[str, Path]) -> Tuple[str, List[Event]]:
    return predictions_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Signal fusion (Epic 2 story 3 — the ``fuse`` pipeline stage)
# ---------------------------------------------------------------------------

# Overall-confidence tiers. Story AC: OCR-only < single-signal < multi-signal.
CONF_MADE_TRIPLE = 0.93  # trajectory + ball_in_basket + score delta
CONF_MADE_DOUBLE = 0.85  # (trajectory | ball_in_basket) + score delta
CONF_UNKNOWN_TRAJECTORY_PENALTY = 0.10  # geometry was inconclusive ("unknown")
CONF_MADE_UNCONFIRMED_DOUBLE = 0.75  # traj + bib, scorebug unavailable
CONF_MADE_UNCONFIRMED_TRAJECTORY = 0.60  # trajectory only, scorebug unavailable
CONF_MADE_UNCONFIRMED_BIB = 0.55  # ball_in_basket only, scorebug unavailable
CONF_MISS = 0.70  # clean trajectory miss (scorebug working: no delta corroborates)
CONF_MISS_NO_SCOREBUG = 0.65  # trajectory miss, scorebug unavailable
CONF_MISS_CONFLICT = 0.55  # make geometry but no delta -> downgraded to miss
CONF_RESYNC = 0.30  # wide-window catch-up event

_MAX_SINGLE_EVENT_DELTA = 3

# --- Shot type (epic-4 story-1) ---
# A +1 delta this soon after a +2/+3 delta is an and-one free throw: the FG
# and the FT must stay two separate events, and a shot candidate near both
# deltas must confirm against the field goal, never the free throw.
AND_ONE_GAP_SEC = 3.0

# A clean trajectory miss this close to a delta-confirmed OCR-only make is the
# same shot the scoreboard just confirmed: the trajectory misjudged the make as
# a miss and OCR lag pushed the score delta past ``confirm_window_sec`` (≈ the
# 2.0 s window + the ~1.5 s scorebug lag). The phantom miss is dropped so the
# make surfaces once — see ``_suppress_misses_shadowed_by_ocr_makes``.
MISS_ABSORB_WINDOW_SEC = 3.5

# A scorer lower-third graphic (number + name, read by the scorer stage) is
# attributed to a made basket within this many seconds of the graphic's span.
# The broadcast shows it right around the scoring play; the window is generous
# because it can appear a beat before or linger well after.
SCORER_MATCH_WINDOW_SEC = 10.0

# Commentary lags the play by 1-3 s and references it for several more, so ASR
# cues are matched to an event within this window. ASR only corroborates
# (adds an "asr" evidence tag, and a small jersey-confidence boost when the
# spoken name confirms the graphic) — it never creates or changes an event.
ASR_WINDOW_SEC = 8.0
ASR_JERSEY_BOOST = 0.02
MIN_SPOKEN_NAME_LEN = 5  # a spoken word this long matching the graphic name is a real cross-check

# Free-throw scene corroboration (pure heuristic over teams tracks + detect
# arrays; see ft_scene_corroborated for the full rules).
FT_SCENE_WINDOW_SEC = 3.0  # tracks are examined +/- this around the event time
FT_SCENE_MIN_PLAYERS = 4  # near-static players required near one rim
FT_SCENE_MAX_MOVE_FRAC = 0.6  # max center travel, as a fraction of median box height
FT_SCENE_RIM_RADIUS_WIDTHS = 8.0  # player center within this many rim-widths of a rim center
FT_SCENE_CONF_BOOST = 0.12  # added to a corroborated OCR-only FT's overall/outcome confidence
FT_SCENE_CONF_CAP = 0.55  # boosted OCR-only FT never reaches the trajectory-only tiers


def _delta_type(points: int) -> str:
    """Primary shot-type rule (epic-4 story-1): +1 -> free throw, +2/+3 ->
    shot (2PT/3PT distinguished by ``points`` — arithmetic, authoritative
    whenever the score bug is visible)."""
    return EVENT_TYPE_FREE_THROW if points == 1 else EVENT_TYPE_SHOT


def _candidate_time(cand: Dict[str, Any]) -> float:
    """Rule 2: the rim-crossing time owns the timestamp when available."""
    return float(cand["t_rim"]) if cand.get("t_rim") is not None else float(cand["t"])


def _and_one_ft_indices(deltas: List[Dict[str, Any]]) -> set:
    """Indices of +1 deltas in and-one position: a +2/+3 delta precedes them
    within ``AND_ONE_GAP_SEC``. Such a +1 is the bonus free throw — matching
    deprioritizes it so the field-goal delta confirms the shot candidate."""
    out: set = set()
    ordered = sorted(range(len(deltas)), key=lambda i: float(deltas[i]["t"]))
    for pos, di in enumerate(ordered):
        if int(deltas[di]["delta"]) != 1:
            continue
        t_ft = float(deltas[di]["t"])
        for dj in ordered[:pos]:
            if int(deltas[dj]["delta"]) in (2, 3) and 0.0 <= t_ft - float(deltas[dj]["t"]) <= AND_ONE_GAP_SEC:
                out.add(di)
                break
    return out


def _match_deltas(
    candidates: List[Dict[str, Any]],
    deltas: List[Dict[str, Any]],
    window_sec: float,
) -> Dict[int, int]:
    """Greedy 1:1 candidate<->delta matching by time distance.

    Only make-capable candidates (kind "make" or "unknown") may consume a
    delta; a clean trajectory miss never does — if a delta lands near a miss
    it belongs to some undetected make and surfaces as an OCR-only event.

    And-one guard (epic-4 story-1): a +1 delta that follows a +2/+3 within
    ``AND_ONE_GAP_SEC`` is matched only after every other delta in range
    (a ``window_sec`` penalty on its greedy rank). A lone shot candidate
    between the two deltas therefore confirms against the field goal, and
    the +1 stays a separate free-throw event — the pair never merges.
    """
    and_one_fts = _and_one_ft_indices(deltas)
    pairs: List[Tuple[float, int, int]] = []
    for ci, cand in enumerate(candidates):
        if cand["kind"] not in ("make", "unknown"):
            continue
        t_c = _candidate_time(cand)
        for di, delta in enumerate(deltas):
            distance = abs(float(delta["t"]) - t_c)
            if distance <= window_sec:
                rank = distance + (window_sec if di in and_one_fts else 0.0)
                pairs.append((rank, ci, di))
    pairs.sort()
    cand_to_delta: Dict[int, int] = {}
    used_deltas: set = set()
    for _rank, ci, di in pairs:
        if ci in cand_to_delta or di in used_deltas:
            continue
        cand_to_delta[ci] = di
        used_deltas.add(di)
    return cand_to_delta


def _suppress_misses_shadowed_by_ocr_makes(
    entries: List[Tuple["Event", Optional[Dict[str, Any]], Optional[Dict[str, Any]]]],
    window_sec: float,
    debug: Dict[str, Any],
) -> None:
    """Drop a clean trajectory miss that sits within ``window_sec`` of a
    delta-confirmed OCR-only make (a delta that matched no shot candidate).

    Such a delta found no make candidate of its own, and a lone trajectory
    miss beside it is that same shot mis-scored by the trajectory — the
    scoreboard proves it went in. Suppressing the miss prevents a phantom
    missed shot next to the make; real-broadcast OCR lag routinely places the
    delta 2-3.5 s past the trajectory, beyond ``confirm_window_sec``, so the
    two never merged in ``_match_deltas``. The make is left untouched (its own
    scorebug evidence, delta timestamp, delta team) — the trajectory said
    *miss*, so it is not claimed as evidence *for* the make. Mutates
    ``entries`` in place.
    """
    ocr_make_times = [
        event.t
        for event, cand, delta in entries
        if delta is not None and cand is None and event.outcome == OUTCOME_MADE
    ]
    if not ocr_make_times:
        return
    kept: List[Tuple["Event", Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = []
    for entry in entries:
        event, _cand, delta = entry
        if (
            event.outcome == OUTCOME_MISSED
            and delta is None
            and any(abs(mt - event.t) <= window_sec for mt in ocr_make_times)
        ):
            debug["dropped"].append({"reason": "miss_shadowed_by_confirmed_make", "t": event.t})
            continue
        kept.append(entry)
    entries[:] = kept


def ft_scene_corroborated(
    t: float,
    tracks: Optional[List[Dict[str, Any]]],
    detect_arrays: Optional[Dict[str, Any]],
    rims: Optional[List[Dict[str, Any]]],
    window_sec: float = FT_SCENE_WINDOW_SEC,
    min_players: int = FT_SCENE_MIN_PLAYERS,
    max_move_frac: float = FT_SCENE_MAX_MOVE_FRAC,
    rim_radius_widths: float = FT_SCENE_RIM_RADIUS_WIDTHS,
) -> bool:
    """Free-throw scene heuristic (epic-4 story-1), pure and detector-free.

    True when the player layout around time ``t`` looks like a free throw:
    at least ``min_players`` tracks that (a) have >= 2 player detections
    inside ``t +/- window_sec``, (b) are nearly static there — total center
    travel <= ``max_move_frac`` of the track's median box height (players
    line up and stand during a FT), and (c) cluster near one rim — mean
    center within ``rim_radius_widths`` rim-widths of that rim's center
    (roughly the paint on a broadcast frame).

    Inputs are the teams-stage ``tracks`` (det_rows index the detect npz),
    the detect-stage arrays (boxes/class_ids/frame_idx/frame_t), and the
    shots-stage ``rims`` list. Any missing input -> False (never corroborate
    without evidence).
    """
    if not tracks or not rims or detect_arrays is None:
        return False
    required = ("boxes", "class_ids", "frame_idx", "frame_t")
    if any(key not in detect_arrays for key in required):
        return False
    boxes = detect_arrays["boxes"]
    class_ids = detect_arrays["class_ids"]
    frame_idx = detect_arrays["frame_idx"]
    frame_t = detect_arrays["frame_t"]
    n_rows = len(class_ids)
    lo, hi = t - window_sec, t + window_sec

    static_per_rim: Dict[int, int] = {}
    for track in tracks:
        xs: List[float] = []
        ys: List[float] = []
        heights: List[float] = []
        for row in track.get("det_rows", []):
            row = int(row)
            if not (0 <= row < n_rows) or int(class_ids[row]) != 3:  # canonical player class id
                continue
            if not (lo <= float(frame_t[int(frame_idx[row])]) <= hi):
                continue
            x1, y1, x2, y2 = (float(v) for v in boxes[row])
            xs.append((x1 + x2) / 2.0)
            ys.append((y1 + y2) / 2.0)
            heights.append(y2 - y1)
        if len(xs) < 2:
            continue
        heights.sort()
        median_h = heights[len(heights) // 2]
        if median_h <= 0:
            continue
        travel = ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5
        if travel > max_move_frac * median_h:
            continue  # moving player — not a free-throw lineup
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        for rim in rims:
            rx1, ry1, rx2, ry2 = (float(v) for v in rim["box"])
            rim_w = max(rx2 - rx1, 1.0)
            rcx, rcy = (rx1 + rx2) / 2.0, (ry1 + ry2) / 2.0
            if ((mx - rcx) ** 2 + (my - rcy) ** 2) ** 0.5 <= rim_radius_widths * rim_w:
                rim_id = int(rim.get("rim_id", 0))
                static_per_rim[rim_id] = static_per_rim.get(rim_id, 0) + 1
                break
    return any(count >= min_players for count in static_per_rim.values())


def _in_resync_window(t: float, resyncs: List[Dict[str, Any]]) -> bool:
    for event in resyncs:
        t_end = event.get("t_end")
        if float(event["t"]) <= t <= float(t_end if t_end is not None else event["t"]):
            return True
    return False


def fuse_signals(
    shots: Optional[Dict[str, Any]],
    scorebug: Optional[Dict[str, Any]],
    teams: Optional[Dict[str, Any]] = None,
    jersey: Optional[Dict[str, Any]] = None,
    confirm_window_sec: float = 2.0,
    jersey_min_conf: float = 0.5,
    detect_arrays: Optional[Dict[str, Any]] = None,
    scorer: Optional[Dict[str, Any]] = None,
    asr: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Event], Dict[str, Any]]:
    """Fuse shots + scorebug (+ teams + jersey) stage outputs into events.

    Fusion truth table (T = trajectory kind, B = ball_in_basket signal,
    D = in-vision score delta 1-3 within ``confirm_window_sec``; "sb down" =
    scorebug unavailable — output missing, bug not found, score fields not
    found, or the candidate sits inside a resync (bug-hidden) window)::

        T        B    D    -> event                 points  evidence              overall
        -------- ---- ---- ------------------------ ------- --------------------- -------
        make     yes  yes  shot/FT made             delta   traj + bib + scorebug 0.93
        make     no   yes  shot/FT made             delta   traj + scorebug       0.85
        none     yes  yes  shot/FT made             delta   bib + scorebug        0.85
        unknown  no   yes  shot/FT made             delta   traj + scorebug       0.75
        make     yes  no   shot missed (conflict)   null    traj + bib            0.55
        make     no   no   shot missed (conflict)   null    traj                  0.55
        none     yes  no   shot missed (conflict)   null    bib                   0.55
        miss     no   no   shot missed              null    traj                  0.70
        unknown  no   no   (no event)               —       —                     —
        none     no   yes  shot/FT made (OCR-only)  delta   scorebug              <=0.50
        resync or delta>3  score_change, wide       null    scorebug              0.30
        any-make any  sb down -> shot made          null    traj and/or bib       0.55-0.75
        miss     no   sb down -> shot missed        null    traj                  0.65

    Additional rules:

    * ``suppressed`` candidates (window spans a camera cut) are ignored.
    * ``possible_replay`` candidates are dropped unless a delta confirms
      them independently (a replayed make never has a second delta).
    * Free throws: delta == 1 -> type "free_throw", else "shot" (epic-4
      story-1 primary rule — arithmetic on the delta).
    * And-one guard: a +1 delta within ``AND_ONE_GAP_SEC`` of a preceding
      +2/+3 is matched last (see ``_match_deltas``) — the FG and the bonus
      FT always come out as two events. Consecutive +1 +1 deltas likewise
      stay two free-throw events with their own timestamps.
    * OCR-only +1 events get a confidence boost (+``FT_SCENE_CONF_BOOST``,
      capped at ``FT_SCENE_CONF_CAP``) and an ``"ft_scene"`` evidence tag
      when ``ft_scene_corroborated`` recognizes a free-throw lineup around
      the event time (requires ``detect_arrays`` + teams tracks + rims).
    * Missed shots carry ``points: null`` and type "shot" — 2PT vs 3PT is
      NEVER guessed without court position (homography deferred); each such
      event adds a ``fusion_debug`` warning.
    * A clean trajectory miss within ``MISS_ABSORB_WINDOW_SEC`` of a
      delta-confirmed OCR-only make is dropped: the scoreboard proves that
      shot scored (OCR lag placed the delta past ``confirm_window_sec``), so
      the make surfaces once rather than as a phantom miss beside it.
    * Resync / delta > 3 scorebug events -> low-confidence wide-window
      ``score_change`` events, points null — never a single fabricated
      basket. Candidates inside the hidden window are unconfirmable, so
      they keep their trajectory verdict (made, points null).
    * Team (rule 4): confirmed makes with a shooter track vote
      cluster(shooter) = scorebug team; the majority fixes the cluster->team
      map which then applies to every event with a shooter cluster.
      Confidence scales with the vote margin. Unresolvable -> team from
      scorebug alone (evidence then lacks "teams" — that is the note).
    * Jersey (rule 5): shooter track's voted jersey, null below
      ``jersey_min_conf``.

    Returns (events sorted by t, debug dict for fusion_debug.json).
    """
    debug: Dict[str, Any] = {"dropped": [], "matches": [], "votes": [], "cluster_to_team": {}, "warnings": []}

    all_candidates = list((shots or {}).get("shot_candidates", []))
    candidates = [c for c in all_candidates if not c.get("suppressed")]
    candidates.sort(key=_candidate_time)
    n_suppressed = len(all_candidates) - len(candidates)
    if n_suppressed:
        debug["dropped"].append({"reason": "suppressed_spans_cut", "count": n_suppressed})

    scorebug_available = bool(scorebug is not None and scorebug.get("bug_found") and scorebug.get("score_fields_found"))
    debug["scorebug_available"] = scorebug_available
    sb_events = list(scorebug.get("events", [])) if scorebug_available else []
    deltas = [e for e in sb_events if not e.get("resync") and 1 <= int(e["delta"]) <= _MAX_SINGLE_EVENT_DELTA]
    wides = [e for e in sb_events if e.get("resync") or int(e["delta"]) > _MAX_SINGLE_EVENT_DELTA]
    resyncs = [e for e in sb_events if e.get("resync")]

    cand_to_delta = _match_deltas(candidates, deltas, confirm_window_sec)
    used_deltas = set(cand_to_delta.values())

    # entries: (Event, source candidate | None, confirming delta | None)
    entries: List[Tuple[Event, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = []

    for ci, cand in enumerate(candidates):
        t_event = round(_candidate_time(cand), 3)
        signals = [s for s in cand.get("signals", []) if s in ("trajectory", "ball_in_basket")]
        di = cand_to_delta.get(ci)
        if di is not None:
            delta = deltas[di]
            points = int(delta["delta"])
            d_conf = float(delta.get("confidence", 0.5))
            overall = CONF_MADE_TRIPLE if len(signals) >= 2 else CONF_MADE_DOUBLE
            if cand["kind"] == "unknown":
                overall -= CONF_UNKNOWN_TRAJECTORY_PENALTY
            confidence = {
                "overall": round(overall, 3),
                "outcome": round(overall, 3),
                "points": round(min(0.98, 0.8 + 0.15 * d_conf), 3),
            }
            team = delta.get("team")
            if team is not None:
                confidence["team"] = round(0.55 + 0.25 * d_conf, 3)
            event = Event(
                t=t_event,
                type=_delta_type(points),
                outcome=OUTCOME_MADE,
                team=team,
                points=points,
                confidence=confidence,
                evidence=signals + ["scorebug"],
            )
            entries.append((event, cand, delta))
            debug["matches"].append({"candidate_id": cand.get("candidate_id"), "delta_t": delta["t"]})
            continue

        # No confirming delta.
        if cand.get("possible_replay"):
            # Rule: a replayed make/miss fires the trajectory again but never
            # brings a second score delta -> drop, never a fabricated event.
            debug["dropped"].append({"reason": "possible_replay", "candidate_id": cand.get("candidate_id")})
            continue

        unconfirmable = not scorebug_available or _in_resync_window(t_event, resyncs)
        if cand["kind"] == "make":
            if unconfirmable:
                # Scorebug can't confirm or deny -> trajectory-only make.
                if len(signals) >= 2:
                    overall = CONF_MADE_UNCONFIRMED_DOUBLE
                elif "trajectory" in signals:
                    overall = CONF_MADE_UNCONFIRMED_TRAJECTORY
                else:
                    overall = CONF_MADE_UNCONFIRMED_BIB
                outcome = OUTCOME_MADE
            else:
                # Scorebug was watching and the score never moved -> rule 3:
                # shot candidate with no delta is a miss (conflicting
                # geometry keeps the confidence modest).
                overall = CONF_MISS_CONFLICT
                outcome = OUTCOME_MISSED
        elif cand["kind"] == "miss":
            overall = CONF_MISS if scorebug_available else CONF_MISS_NO_SCOREBUG
            outcome = OUTCOME_MISSED
        else:  # "unknown" with no delta: not enough evidence for any event
            debug["dropped"].append({"reason": "unknown_no_delta", "candidate_id": cand.get("candidate_id")})
            continue
        if outcome == OUTCOME_MISSED:
            # Epic-4 story-1: without a delta there is no points signal, and
            # 2PT vs 3PT must never be guessed without court position.
            debug["warnings"].append(
                f"event t={t_event}: missed shot with unknown 2PT/3PT type — "
                "shooter court position unknown (homography deferred)"
            )
        event = Event(
            t=t_event,
            type=EVENT_TYPE_SHOT,
            outcome=outcome,
            points=None,
            confidence={"overall": round(overall, 3), "outcome": round(overall, 3)},
            evidence=list(signals),
        )
        entries.append((event, cand, None))

    # Rule 3: score delta with no candidate -> OCR-only event, reduced conf.
    rims = list((shots or {}).get("rims", []))
    for di, delta in enumerate(deltas):
        if di in used_deltas:
            continue
        points = int(delta["delta"])
        d_conf = float(delta.get("confidence", 0.5))
        overall = round(0.4 + 0.1 * d_conf, 3)  # always below single-signal tiers
        evidence = ["scorebug"]
        t_delta = round(float(delta["t"]), 3)
        if points == 1 and ft_scene_corroborated(t_delta, (teams or {}).get("tracks"), detect_arrays, rims):
            # Epic-4 story-1: a free-throw lineup (static players clustered at
            # a rim) corroborates an OCR-only +1 event.
            overall = round(min(FT_SCENE_CONF_CAP, overall + FT_SCENE_CONF_BOOST), 3)
            evidence.append("ft_scene")
            debug["matches"].append({"ft_scene": True, "delta_t": delta["t"]})
        confidence = {"overall": overall, "outcome": overall, "points": round(0.6 + 0.2 * d_conf, 3)}
        team = delta.get("team")
        if team is not None:
            confidence["team"] = round(0.5 + 0.2 * d_conf, 3)
        event = Event(
            t=t_delta,
            type=_delta_type(points),
            outcome=OUTCOME_MADE,
            team=team,
            points=points,
            confidence=confidence,
            evidence=evidence,
        )
        entries.append((event, None, delta))

    # Resync / delta>3: wide-window catch-up events, never a single basket.
    for wide in wides:
        team = wide.get("team")
        confidence = {"overall": CONF_RESYNC}
        if team is not None:
            confidence["team"] = CONF_RESYNC
        t_end = wide.get("t_end")
        event = Event(
            t=round(float(wide["t"]), 3),
            t_end=round(float(t_end), 3) if t_end is not None else None,
            type=EVENT_TYPE_SCORE_CHANGE,
            outcome=None,
            team=team,
            points=None,
            confidence=confidence,
            evidence=["scorebug"],
        )
        entries.append((event, None, wide))

    _suppress_misses_shadowed_by_ocr_makes(entries, MISS_ABSORB_WINDOW_SEC, debug)
    _apply_team_and_jersey(entries, teams, jersey, jersey_min_conf, debug)
    _attach_scorer_graphic(entries, scorer, debug)
    _corroborate_with_asr(entries, scorer, asr, debug)

    events = sorted((entry[0] for entry in entries), key=lambda e: (e.t, e.type))
    return events, debug


def _shooter_track(cand: Optional[Dict[str, Any]], row_to_track: Dict[int, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Rule 4 shooter attribution: the track owning the player detection
    nearest the last ball position (hint computed by the shots stage)."""
    if cand is None:
        return None
    row = cand.get("nearest_player_det_row")
    if row is None:
        return None
    return row_to_track.get(int(row))


def _resolve_cluster_teams(votes: Dict[Tuple[int, str], int]) -> Tuple[Dict[int, str], Dict[int, float]]:
    """Majority vote per cluster -> (cluster -> team, cluster -> margin).

    Margin is (top - runner_up) / cluster_total in [0, 1]. Ties resolve to
    nothing; two clusters claiming the same team keep only the higher-margin
    claim (the map must stay self-consistent)."""
    clusters = {c for c, _ in votes}
    team_names = {t for _, t in votes}
    mapping: Dict[int, str] = {}
    margins: Dict[int, float] = {}
    for cluster in clusters:
        tally = sorted(((votes.get((cluster, t), 0), t) for t in team_names), reverse=True)
        top_votes, top_team = tally[0]
        runner_up = tally[1][0] if len(tally) > 1 else 0
        total = sum(v for v, _ in tally)
        if top_votes == 0 or top_votes == runner_up:
            continue
        mapping[cluster] = top_team
        margins[cluster] = (top_votes - runner_up) / total
    claimed: Dict[str, List[int]] = {}
    for cluster, team in mapping.items():
        claimed.setdefault(team, []).append(cluster)
    for team, claimers in claimed.items():
        if len(claimers) > 1:
            keep = max(claimers, key=lambda c: margins[c])
            for cluster in claimers:
                if cluster != keep:
                    mapping.pop(cluster)
                    margins.pop(cluster)
    return mapping, margins


def _apply_team_and_jersey(
    entries: List[Tuple[Event, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]],
    teams: Optional[Dict[str, Any]],
    jersey: Optional[Dict[str, Any]],
    jersey_min_conf: float,
    debug: Dict[str, Any],
) -> None:
    """Fusion rules 4 + 5: resolve anonymous kit clusters to team names by
    voting over confirmed makes, then attach team + jersey to every event
    with a shooter track. Mutates the events in ``entries`` in place."""
    if teams is None:
        debug["warnings"].append("teams output missing — team attribution from scorebug alone")
    if jersey is None:
        debug["warnings"].append("jersey output missing — jersey attribution skipped")

    row_to_track: Dict[int, Dict[str, Any]] = {}
    for track in (teams or {}).get("tracks", []):
        for row in track.get("det_rows", []):
            row_to_track[int(row)] = track

    # Vote cluster(shooter) = team(scorebug) over delta-confirmed events.
    votes: Dict[Tuple[int, str], int] = {}
    for event, cand, delta in entries:
        if delta is None or event.outcome != OUTCOME_MADE:
            continue
        team_name = delta.get("team")
        track = _shooter_track(cand, row_to_track)
        if team_name is None or track is None or track.get("cluster") is None:
            continue
        key = (int(track["cluster"]), str(team_name))
        votes[key] = votes.get(key, 0) + 1
    mapping, margins = _resolve_cluster_teams(votes)
    debug["votes"] = [{"cluster": c, "team": t, "votes": n} for (c, t), n in sorted(votes.items())]
    debug["cluster_to_team"] = {str(c): t for c, t in mapping.items()}

    jersey_by_track: Dict[Any, Dict[str, Any]] = {rec["track_id"]: rec for rec in (jersey or {}).get("tracks", [])}

    for event, cand, delta in entries:
        track = _shooter_track(cand, row_to_track)
        if track is None:
            continue
        cluster = track.get("cluster")
        if cluster is not None and int(cluster) in mapping:
            resolved = mapping[int(cluster)]
            margin = margins[int(cluster)]
            conflict = event.team is not None and event.team != resolved
            event.team = resolved
            event.confidence["team"] = 0.4 if conflict else round(min(0.9, 0.5 + 0.4 * margin), 3)
            if "teams" not in event.evidence:
                event.evidence.append("teams")
            if conflict:
                debug["warnings"].append(
                    f"event t={event.t}: scorebug team disagreed with cluster map — cluster map wins"
                )
        record = jersey_by_track.get(track.get("track_id"))
        if record and record.get("jersey") is not None and float(record.get("confidence", 0.0)) >= jersey_min_conf:
            event.jersey = str(record["jersey"])
            event.confidence["jersey"] = round(float(record["confidence"]), 3)
            if "jersey" not in event.evidence:
                event.evidence.append("jersey")


def _attach_scorer_graphic(
    entries: List[Tuple[Event, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]],
    scorer: Optional[Dict[str, Any]],
    debug: Dict[str, Any],
) -> None:
    """Attach the scorer lower-third's jersey number to a made basket.

    The broadcast graphic names the scorer directly (number + person), so it
    fills the jersey even on scoreboard-only makes that have no shooter track —
    the common case the shooter-based path (rule 5) cannot reach. It is the
    stronger signal, so it overrides any shooter-track jersey. A graphic is
    matched to a make within ``SCORER_MATCH_WINDOW_SEC`` of its span; when two
    different scorers are equally present near one make, the jersey is left as
    is (prefer null over wrong). Mutates the events in ``entries`` in place.
    """
    features = list((scorer or {}).get("features") or [])
    if not features:
        return
    for event, _cand, _delta in entries:
        if event.outcome != OUTCOME_MADE:
            continue
        near = [
            f
            for f in features
            if f["t_start"] - SCORER_MATCH_WINDOW_SEC <= event.t <= f["t_end"] + SCORER_MATCH_WINDOW_SEC
        ]
        if not near:
            continue
        near.sort(key=lambda f: f["n_frames"], reverse=True)
        best = near[0]
        if len(near) > 1 and best["number"] != near[1]["number"] and near[1]["n_frames"] >= best["n_frames"]:
            continue  # two equally-present scorers -> ambiguous, leave jersey null
        event.jersey = str(best["number"])
        event.confidence["jersey"] = float(best.get("confidence", 0.0))
        if "scorer_graphic" not in event.evidence:
            event.evidence.append("scorer_graphic")
        debug.setdefault("scorer_matches", []).append(
            {"t": event.t, "number": best["number"], "name": best.get("name")}
        )


def _name_spoken(graphic_name: str, spoken_text: str) -> bool:
    """A commentary word (>= MIN_SPOKEN_NAME_LEN letters) that is a substring of
    the graphic's concatenated name — "Perry" confirms the graphic "TYLORPERRY",
    robust to the first-name spelling ("Tyler" vs "Tylor")."""
    g = re.sub(r"[^a-z]", "", graphic_name.lower())
    return any(len(w) >= MIN_SPOKEN_NAME_LEN and w in g for w in re.findall(r"[a-z]+", spoken_text.lower()))


def _corroborate_with_asr(
    entries: List[Tuple[Event, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]],
    scorer: Optional[Dict[str, Any]],
    asr: Optional[Dict[str, Any]],
    debug: Dict[str, Any],
) -> None:
    """Corroborate events with the commentary (never create or change one).

    Cross-validates the scorer graphic's name against the spoken name (a small
    jersey-confidence bump when they agree), and tags an ``"asr"`` evidence when
    the commentary calls the event's outcome / shot type near its time. Mutates
    the events in ``entries`` in place.
    """
    if asr is None or asr.get("skipped"):
        return
    segments = list(asr.get("segments") or [])
    cues = list(asr.get("cues") or [])
    if not segments and not cues:
        return
    features = list((scorer or {}).get("features") or [])
    for event, _cand, _delta in entries:
        lo, hi = event.t - ASR_WINDOW_SEC, event.t + ASR_WINDOW_SEC
        near_text = " ".join(s["text"] for s in segments if lo <= float(s.get("t_start", 0.0)) <= hi)
        near_kinds = {c["kind"] for c in cues if lo <= float(c["t"]) <= hi}
        tagged = False

        # Scorer-name cross-validation: the graphic gave the jersey; the spoken
        # name confirms the same player.
        if "scorer_graphic" in event.evidence and event.jersey is not None and near_text:
            match = next(
                (
                    f
                    for f in features
                    if f["number"] == event.jersey
                    and f["t_start"] - SCORER_MATCH_WINDOW_SEC <= event.t <= f["t_end"] + SCORER_MATCH_WINDOW_SEC
                ),
                None,
            )
            if match and _name_spoken(str(match.get("name", "")), near_text):
                event.confidence["jersey"] = round(
                    min(0.99, float(event.confidence.get("jersey", 0.0)) + ASR_JERSEY_BOOST), 3
                )
                tagged = True
                debug.setdefault("asr_matches", []).append(
                    {"t": event.t, "jersey": event.jersey, "name": match.get("name")}
                )

        # Outcome / shot-type corroboration.
        if (
            (event.outcome == OUTCOME_MADE and "make" in near_kinds)
            or (event.outcome == OUTCOME_MISSED and "miss" in near_kinds)
            or (event.points == 3 and "three" in near_kinds)
            or (event.type == EVENT_TYPE_FREE_THROW and "free_throw" in near_kinds)
        ):
            tagged = True

        if tagged and "asr" not in event.evidence:
            event.evidence.append("asr")


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """``fuse`` stage: combine scorebug/shots/teams/jersey caches into the
    final event timeline (predictions format — see module docstring).

    Missing upstream outputs degrade gracefully: no scorebug -> trajectory-
    only events; no shots -> OCR-only events; no teams/jersey -> null
    attributes. An upstream output that is a skipped marker
    (``{"skipped": true, ...}`` — e.g. detect ran with no model) is treated
    exactly like a missing one. Each absence logs a warning. The detect
    ``arrays.npz`` is loaded when present, for free-throw scene
    corroboration of OCR-only +1 events."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    def _optional(stage: str) -> Optional[Dict[str, Any]]:
        try:
            data = ctx.cache.read_json(stage)
        except FileNotFoundError:
            logger.warning("fuse: no cached '%s' output for clip %s — continuing without it", stage, ctx.clip_id)
            return None
        if isinstance(data, dict) and data.get("skipped"):
            logger.warning(
                "fuse: '%s' stage was skipped (%s) — continuing without it", stage, data.get("reason", "no reason")
            )
            return None
        return data

    shots = _optional("shots")
    scorebug = _optional("scorebug")
    teams = _optional("teams")
    jersey = _optional("jersey")
    scorer = _optional("scorer")
    asr = _optional("asr")
    try:
        detect_arrays: Optional[Dict[str, Any]] = ctx.cache.read_arrays("detect")
    except FileNotFoundError:
        detect_arrays = None

    events, debug = fuse_signals(
        shots,
        scorebug,
        teams,
        jersey,
        confirm_window_sec=ctx.settings.fuse_confirm_window_sec,
        jersey_min_conf=ctx.settings.fuse_jersey_min_conf,
        detect_arrays=detect_arrays,
        scorer=scorer,
        asr=asr,
    )
    logger.info("fuse: %d event(s) for clip %s", len(events), ctx.clip_id)
    ctx.cache.write_json(ctx.stage, debug, filename="fusion_debug.json")
    ctx.cache.write_json(ctx.stage, predictions_to_dict(ctx.clip_id, events))  # warm marker last
