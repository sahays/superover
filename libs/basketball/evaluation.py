"""Eval harness logic: manifest loading, event matching, and scoring.

Thin CLI wrapper: ``evals/basketball/run_eval.py``. Kept here so the matcher
and scorers are unit-testable (tests/basketball/test_evaluation.py).

Matching rule (Rung 1, docs/tech/evaluation-strategy.md): greedy 1:1 matching
by time distance within a ±``tolerance_sec`` window; an event's reference
time is its midpoint when ``t_end`` is set, else ``t``.

Verification semantics: each ground-truth event carries a per-attribute
``verified`` map (bool shorthand = all attributes). By default only events
with ``verified.event == true`` are scored; predictions that fall on an
unverified event or inside a ``needs_manual_review`` window are IGNORED
(neither TP nor FP — the labels there are incomplete). ``include_unverified``
scores everything. Predicted scoring events inside a ``no_scoring_expected``
window are always false positives (checked assertions).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

from libs.basketball.timeline import SCORING_EVENT_TYPES, Event

ATTRIBUTES = ("team", "points", "jersey")
VERIFIED_KEYS = ("event", "outcome", "team", "points", "jersey")


# --- Manifest model ---


@dataclass
class GroundTruthEvent:
    event: Event
    verified: Dict[str, bool]
    source: Optional[str] = None
    points_attempted: Optional[int] = None
    note: Optional[str] = None


@dataclass
class Window:
    """A [t, t_end] window attached to a clip-level assertion/flag."""

    clip: str
    t: Optional[float] = None
    t_end: Optional[float] = None
    verified: bool = False
    source: Optional[str] = None
    reason: Optional[str] = None

    def contains(self, t: float) -> bool:
        if self.t is None:  # whole-clip window
            return True
        end = self.t_end if self.t_end is not None else self.t
        return self.t <= t <= end


@dataclass
class ClipTruth:
    name: str
    file: Optional[str] = None
    sha256: Optional[str] = None
    events: List[GroundTruthEvent] = field(default_factory=list)
    no_scoring: List[Window] = field(default_factory=list)
    needs_review: List[Window] = field(default_factory=list)


@dataclass
class Manifest:
    clips: Dict[str, ClipTruth]
    tolerance_sec: float = 2.0
    raw: Dict[str, Any] = field(default_factory=dict)


def _normalize_verified(value: Any) -> Dict[str, bool]:
    """bool -> all keys; dict -> per-key with missing keys defaulting False."""
    if isinstance(value, bool):
        return {key: value for key in VERIFIED_KEYS}
    if isinstance(value, dict):
        return {key: bool(value.get(key, False)) for key in VERIFIED_KEYS}
    raise ValueError(f"'verified' must be a bool or a mapping, got {value!r}")


def load_manifest(path: Union[str, Path]) -> Manifest:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    clips: Dict[str, ClipTruth] = {}
    for name, spec in (data.get("clips") or {}).items():
        spec = spec or {}
        events = []
        for entry in spec.get("events") or []:
            entry = dict(entry)
            verified = _normalize_verified(entry.pop("verified", False))
            source = entry.pop("source", None)
            note = entry.pop("note", None)
            points_attempted = entry.pop("points_attempted", None)
            events.append(
                GroundTruthEvent(
                    event=Event.from_dict(entry),
                    verified=verified,
                    source=source,
                    points_attempted=points_attempted,
                    note=note,
                )
            )
        clips[name] = ClipTruth(
            name=name,
            file=spec.get("file"),
            sha256=spec.get("sha256"),
            events=events,
        )
    for entry in data.get("no_scoring_expected") or []:
        clip = entry["clip"]
        clips.setdefault(clip, ClipTruth(name=clip)).no_scoring.append(
            Window(
                clip=clip,
                t=entry.get("t"),
                t_end=entry.get("t_end"),
                verified=bool(entry.get("verified", False)),
                source=entry.get("source"),
            )
        )
    for entry in data.get("needs_manual_review") or []:
        clip = entry["clip"]
        clips.setdefault(clip, ClipTruth(name=clip)).needs_review.append(
            Window(clip=clip, t=entry.get("t"), t_end=entry.get("t_end"), reason=entry.get("reason"))
        )
    return Manifest(clips=clips, tolerance_sec=float(data.get("tolerance_sec", 2.0)), raw=data)


# --- Matching ---


def match_events(
    predicted: List[Event], truth: List[Event], tolerance_sec: float
) -> Tuple[List[Tuple[int, int, float]], List[int], List[int]]:
    """Greedy 1:1 matching by |time distance| within ±tolerance.

    Returns (matches [(pred_idx, truth_idx, distance)], unmatched pred
    indices, unmatched truth indices). Reference time per event: midpoint if
    t_end is set, else t.
    """
    candidates = []
    for p_idx, pred in enumerate(predicted):
        for t_idx, true in enumerate(truth):
            dist = abs(pred.midpoint - true.midpoint)
            if dist <= tolerance_sec:
                candidates.append((dist, p_idx, t_idx))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    matches: List[Tuple[int, int, float]] = []
    used_pred: Set[int] = set()
    used_truth: Set[int] = set()
    for dist, p_idx, t_idx in candidates:
        if p_idx in used_pred or t_idx in used_truth:
            continue
        used_pred.add(p_idx)
        used_truth.add(t_idx)
        matches.append((p_idx, t_idx, dist))
    unmatched_pred = [i for i in range(len(predicted)) if i not in used_pred]
    unmatched_truth = [i for i in range(len(truth)) if i not in used_truth]
    return matches, unmatched_pred, unmatched_truth


# --- Scoring ---


@dataclass
class AttributeScore:
    correct: int = 0
    total: int = 0

    @property
    def accuracy(self) -> Optional[float]:
        return self.correct / self.total if self.total else None


@dataclass
class ClipScore:
    clip: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    ignored: int = 0  # predictions on unverified events / needs-review windows
    truth_count: int = 0
    pred_count: int = 0
    attributes: Dict[str, AttributeScore] = field(default_factory=lambda: {a: AttributeScore() for a in ATTRIBUTES})
    assertion_violations: List[str] = field(default_factory=list)
    assertion_checks: int = 0

    @property
    def precision(self) -> Optional[float]:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else None

    @property
    def recall(self) -> Optional[float]:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else None

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


def _attr_equal(attribute: str, predicted: Any, truth: Any) -> bool:
    if attribute == "jersey":
        return str(predicted) == str(truth)
    return predicted == truth


def score_clip(
    clip_truth: ClipTruth,
    predicted: List[Event],
    tolerance_sec: float,
    include_unverified: bool = False,
) -> ClipScore:
    """Score one clip's predicted scoring events against its ground truth."""
    score = ClipScore(clip=clip_truth.name)
    preds = [e for e in predicted if e.type in SCORING_EVENT_TYPES]
    score.pred_count = len(preds)

    eligible: List[GroundTruthEvent] = []
    shadow: List[GroundTruthEvent] = []
    for gt in clip_truth.events:
        if include_unverified or gt.verified.get("event", False):
            eligible.append(gt)
        else:
            shadow.append(gt)
    score.truth_count = len(eligible)

    # no_scoring_expected assertions: any predicted scoring event inside the
    # window is a false positive, regardless of other ignore rules.
    violating: Set[int] = set()
    for window in clip_truth.no_scoring:
        score.assertion_checks += 1
        for idx, pred in enumerate(preds):
            if window.contains(pred.midpoint):
                violating.add(idx)
                span = "whole clip" if window.t is None else f"[{window.t:g}, {window.t_end:g}]"
                score.assertion_violations.append(
                    f"{clip_truth.name}: predicted {pred.type} at t={pred.t:g} inside no-scoring window {span}"
                )

    matches, unmatched_pred, unmatched_truth = match_events(preds, [gt.event for gt in eligible], tolerance_sec)
    score.tp = len(matches)
    score.fn = len(unmatched_truth)

    # Unmatched predictions: violations are always FP; the rest are ignored
    # when they land on an unverified event or a needs-manual-review window
    # (labels there are incomplete), FP otherwise.
    shadow_events = [gt.event for gt in shadow]
    for idx in unmatched_pred:
        if idx in violating:
            score.fp += 1
            continue
        pred = preds[idx]
        on_shadow = any(abs(pred.midpoint - ev.midpoint) <= tolerance_sec for ev in shadow_events)
        in_review = any(w.contains(pred.midpoint) for w in clip_truth.needs_review)
        if on_shadow or in_review:
            score.ignored += 1
        else:
            score.fp += 1

    # Attribute accuracy on matched events: scored only where ground truth
    # has a value and (by default) the attribute is human-verified.
    for p_idx, t_idx, _dist in matches:
        pred, gt = preds[p_idx], eligible[t_idx]
        for attribute in ATTRIBUTES:
            truth_value = getattr(gt.event, attribute)
            if truth_value is None:
                continue
            if not include_unverified and not gt.verified.get(attribute, False):
                continue
            stat = score.attributes[attribute]
            stat.total += 1
            if _attr_equal(attribute, getattr(pred, attribute), truth_value):
                stat.correct += 1
    return score


def aggregate_scores(scores: List[ClipScore]) -> ClipScore:
    total = ClipScore(clip="TOTAL")
    for s in scores:
        total.tp += s.tp
        total.fp += s.fp
        total.fn += s.fn
        total.ignored += s.ignored
        total.truth_count += s.truth_count
        total.pred_count += s.pred_count
        total.assertion_checks += s.assertion_checks
        total.assertion_violations.extend(s.assertion_violations)
        for attribute in ATTRIBUTES:
            total.attributes[attribute].correct += s.attributes[attribute].correct
            total.attributes[attribute].total += s.attributes[attribute].total
    return total


# --- Reporting ---


def _fmt(value: Optional[float]) -> str:
    return f"{value:.2f}" if value is not None else "-"


def _fmt_attr(stat: AttributeScore) -> str:
    if not stat.total:
        return "-"
    return f"{stat.correct}/{stat.total} ({stat.accuracy:.0%})"


def render_markdown(scores: List[ClipScore], include_unverified: bool, tolerance_sec: float) -> str:
    """Per-clip + aggregate results as one Markdown table (PR-paste ready)."""
    total = aggregate_scores(scores)
    lines = [
        f"### Basketball eval — scoring events (tolerance ±{tolerance_sec:g} s, "
        f"{'all rows' if include_unverified else 'verified rows only'})",
        "",
        "| Clip | GT | Pred | TP | FP | FN | Ign | P | R | F1 | Team | Points | Jersey |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scores + [total]:
        name = f"**{s.clip}**" if s is total else s.clip
        lines.append(
            f"| {name} | {s.truth_count} | {s.pred_count} | {s.tp} | {s.fp} | {s.fn} | {s.ignored} "
            f"| {_fmt(s.precision)} | {_fmt(s.recall)} | {_fmt(s.f1)} "
            f"| {_fmt_attr(s.attributes['team'])} | {_fmt_attr(s.attributes['points'])} "
            f"| {_fmt_attr(s.attributes['jersey'])} |"
        )
    lines.append("")
    if total.assertion_checks:
        if total.assertion_violations:
            lines.append(f"No-scoring assertions: {len(total.assertion_violations)} VIOLATION(S)")
            lines.extend(f"- {v}" for v in total.assertion_violations)
        else:
            lines.append(f"No-scoring assertions: {total.assertion_checks} checked, all passed")
    return "\n".join(lines)
