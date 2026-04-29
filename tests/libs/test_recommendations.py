"""Tests for libs/engagement/recommendations.py."""

import pytest

from libs.engagement.recommendations import (
    compute_entity_deltas,
    compute_stats,
    find_high_minutes,
    find_low_minutes,
    split_top_deltas,
)
from libs.engagement.scene_extract import Entity


pytestmark = pytest.mark.unit


def _entity(name, *appearances, kind="character"):
    return Entity(name=name, kind=kind, appearances=list(appearances), mention_count=len(appearances))


def test_compute_entity_deltas_basic():
    """Hero appears in high-engagement scenes → large positive delta_pct."""
    series = [
        (0.0, 1.0),
        (10.0, 1.0),
        (20.0, 1.0),  # outside Hero
        (30.0, 9.0),
        (40.0, 9.0),
        (50.0, 9.0),  # inside Hero
        (60.0, 1.0),
        (70.0, 1.0),
        (80.0, 1.0),  # outside Hero
    ]
    entities = [_entity("Hero", (28.0, 55.0))]
    deltas = compute_entity_deltas(series, entities)

    assert len(deltas) == 1
    d = deltas[0]
    assert d.name == "Hero"
    assert d.avg_during == 9.0
    # Overall avg = (1+1+1+9+9+9+1+1+1)/9 = 33/9 ≈ 3.67
    assert abs(d.avg_overall - 33 / 9) < 1e-6
    # delta_pct = (9 - 3.67) / 3.67 * 100 ≈ +145%
    assert d.delta_pct > 100
    assert d.sample_size == 3
    assert d.coverage_sec == 27.0


def test_compute_entity_deltas_negative_for_lulls():
    """Villain appears in low-engagement scenes → negative delta_pct."""
    series = [(t, 1.0 if 30 <= t < 60 else 9.0) for t in range(0, 90, 10)]
    entities = [_entity("Villain", (30.0, 55.0))]
    deltas = compute_entity_deltas(series, entities)
    assert deltas[0].delta_pct < 0


def test_compute_entity_deltas_drops_low_sample_size():
    """An entity with fewer than min_sample_size data points must be dropped."""
    series = [(0.0, 5.0), (60.0, 5.0), (120.0, 5.0)]
    entities = [_entity("Brief", (10.0, 11.0))]  # no points fall in this range
    assert compute_entity_deltas(series, entities) == []


def test_split_top_deltas_orders_by_magnitude():
    # Build deltas manually for clarity
    from libs.engagement.recommendations import EntityDelta

    raw = [
        EntityDelta(
            name="A", kind="character", avg_during=10, avg_overall=5, delta_pct=100, sample_size=3, coverage_sec=30
        ),
        EntityDelta(
            name="B", kind="character", avg_during=20, avg_overall=5, delta_pct=300, sample_size=3, coverage_sec=30
        ),
        EntityDelta(
            name="C", kind="character", avg_during=2, avg_overall=5, delta_pct=-60, sample_size=3, coverage_sec=30
        ),
        EntityDelta(
            name="D", kind="character", avg_during=1, avg_overall=5, delta_pct=-80, sample_size=3, coverage_sec=30
        ),
    ]
    pos, neg = split_top_deltas(raw, n=10)
    assert [d.name for d in pos] == ["B", "A"]  # B is more positive
    assert [d.name for d in neg] == ["D", "C"]  # D is more negative


def test_find_low_minutes_returns_k_lowest():
    # Minute 0: avg=5, Minute 1: avg=1, Minute 2: avg=9, Minute 3: avg=2
    series = [
        (0.0, 5.0),
        (30.0, 5.0),
        (60.0, 1.0),
        (90.0, 1.0),
        (120.0, 9.0),
        (150.0, 9.0),
        (180.0, 2.0),
        (210.0, 2.0),
    ]
    low = find_low_minutes(series, k=2)
    assert [b.minute_index for b in low] == [1, 3]
    assert low[0].avg_score == 1.0


def test_find_high_minutes_returns_k_highest():
    series = [
        (0.0, 5.0),
        (60.0, 9.0),
        (120.0, 1.0),
        (180.0, 7.0),
    ]
    high = find_high_minutes(series, k=2)
    assert [b.minute_index for b in high] == [1, 3]


def test_find_minutes_handles_short_series():
    """Series shorter than k buckets — return whatever we have."""
    series = [(5.0, 5.0)]
    low = find_low_minutes(series, k=10)
    assert len(low) == 1


def test_compute_stats_bundles_everything():
    """compute_stats returns a fully-populated RecommendationStats."""
    series = [(t, 5.0 if 30 <= t < 60 else 1.0) for t in range(0, 90, 10)]
    entities = [_entity("Hero", (30.0, 55.0))]
    stats = compute_stats(series, entities, n_entities=5, n_minutes=2)

    assert stats.overall_avg > 0
    assert stats.target_avg >= stats.overall_avg  # 75th percentile ≥ mean
    assert any(d.name == "Hero" for d in stats.top_positive_entities)
    assert len(stats.high_minutes) <= 2
    assert len(stats.low_minutes) <= 2


def test_compute_stats_handles_empty_input():
    stats = compute_stats([], [])
    assert stats.overall_avg == 0
    assert stats.top_positive_entities == []
