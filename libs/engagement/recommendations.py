"""Deterministic stats that feed the recommendations Gemini call.

Given the parsed BARC `metrics` and the merged `entities` from
`scene_extract.py`, compute three things:

  - entity_deltas: for each entity, the average primary-metric value during
    its appearance ranges vs the overall average. Used to rank which entities
    raised or dropped engagement.

  - low_minutes / high_minutes: the k worst and k best minute-buckets in the
    series, so the LLM can craft per-minute callouts and positive examples.

All pure functions — no Gemini, no I/O.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from libs.engagement.scene_extract import Entity

logger = logging.getLogger(__name__)


@dataclass
class EntityDelta:
    name: str
    kind: str
    avg_during: float
    avg_overall: float
    delta_pct: float  # (avg_during - avg_overall) / avg_overall * 100
    sample_size: int  # number of metric points falling inside appearances
    coverage_sec: float  # total seconds of appearances


@dataclass
class MinuteSlice:
    minute_index: int
    minute_start_sec: float
    minute_end_sec: float
    avg_score: float
    point_count: int


@dataclass
class RecommendationStats:
    """Bundle of deterministic stats handed to the Gemini recommend() call."""

    overall_avg: float
    target_avg: float  # producer's ambition: defaults to top-quartile observed
    top_positive_entities: List[EntityDelta] = field(default_factory=list)
    top_negative_entities: List[EntityDelta] = field(default_factory=list)
    high_minutes: List[MinuteSlice] = field(default_factory=list)
    low_minutes: List[MinuteSlice] = field(default_factory=list)


# ── entity deltas ─────────────────────────────────────────────────


def compute_entity_deltas(
    timeseries: Sequence[Tuple[float, float]],
    entities: Sequence[Entity],
    min_sample_size: int = 2,
) -> List[EntityDelta]:
    """For each entity, compute the avg primary-metric value during its
    appearance ranges vs the overall avg.

    Entities with fewer than `min_sample_size` overlapping data points are
    dropped (the delta is too noisy to be actionable).
    """
    if not timeseries or not entities:
        return []

    overall_avg = _mean(score for _, score in timeseries)
    if overall_avg == 0:
        return []

    out: List[EntityDelta] = []
    for ent in entities:
        if not ent.appearances:
            continue
        scores_during = [
            score for ts, score in timeseries if any(start <= ts <= end for (start, end) in ent.appearances)
        ]
        if len(scores_during) < min_sample_size:
            continue
        avg_during = _mean(scores_during)
        coverage_sec = sum(end - start for (start, end) in ent.appearances)
        delta_pct = (avg_during - overall_avg) / overall_avg * 100.0
        out.append(
            EntityDelta(
                name=ent.name,
                kind=ent.kind,
                avg_during=avg_during,
                avg_overall=overall_avg,
                delta_pct=delta_pct,
                sample_size=len(scores_during),
                coverage_sec=coverage_sec,
            )
        )

    return out


def split_top_deltas(deltas: Sequence[EntityDelta], n: int = 10) -> Tuple[List[EntityDelta], List[EntityDelta]]:
    """Return (top-n positive, top-n negative) ordered by absolute delta_pct."""
    positives = sorted([d for d in deltas if d.delta_pct > 0], key=lambda d: -d.delta_pct)[:n]
    negatives = sorted([d for d in deltas if d.delta_pct < 0], key=lambda d: d.delta_pct)[:n]
    return positives, negatives


# ── minute buckets ────────────────────────────────────────────────


def find_low_minutes(timeseries: Sequence[Tuple[float, float]], k: int = 5) -> List[MinuteSlice]:
    """k lowest-scoring 60-second windows in the series."""
    buckets = _bucket_minutes(timeseries)
    return sorted(buckets, key=lambda b: b.avg_score)[:k]


def find_high_minutes(timeseries: Sequence[Tuple[float, float]], k: int = 5) -> List[MinuteSlice]:
    """k highest-scoring 60-second windows in the series."""
    buckets = _bucket_minutes(timeseries)
    return sorted(buckets, key=lambda b: -b.avg_score)[:k]


def _bucket_minutes(
    timeseries: Sequence[Tuple[float, float]],
) -> List[MinuteSlice]:
    """Group points into 60s windows starting at t=0. Empty buckets dropped."""
    by_index: dict = {}
    for ts, score in timeseries:
        idx = int(ts // 60)
        by_index.setdefault(idx, []).append(score)
    out = [
        MinuteSlice(
            minute_index=idx,
            minute_start_sec=idx * 60.0,
            minute_end_sec=(idx + 1) * 60.0,
            avg_score=_mean(scores),
            point_count=len(scores),
        )
        for idx, scores in by_index.items()
    ]
    out.sort(key=lambda b: b.minute_index)
    return out


# ── orchestration ─────────────────────────────────────────────────


def compute_stats(
    timeseries: Sequence[Tuple[float, float]],
    entities: Sequence[Entity],
    n_entities: int = 10,
    n_minutes: int = 5,
    target_quantile: float = 0.75,
) -> RecommendationStats:
    """Bundle deltas + minute buckets + ambition target for the Gemini call."""
    if not timeseries:
        return RecommendationStats(overall_avg=0.0, target_avg=0.0)

    overall_avg = _mean(score for _, score in timeseries)
    target_avg = _quantile([score for _, score in timeseries], target_quantile)

    deltas = compute_entity_deltas(timeseries, entities)
    positives, negatives = split_top_deltas(deltas, n=n_entities)
    return RecommendationStats(
        overall_avg=overall_avg,
        target_avg=target_avg,
        top_positive_entities=positives,
        top_negative_entities=negatives,
        high_minutes=find_high_minutes(timeseries, k=n_minutes),
        low_minutes=find_low_minutes(timeseries, k=n_minutes),
    )


# ── tiny helpers ──────────────────────────────────────────────────


def _mean(values) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _quantile(values: List[float], q: float) -> float:
    """Linear-interpolation quantile. q in [0, 1]."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = (len(sorted_vals) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac
