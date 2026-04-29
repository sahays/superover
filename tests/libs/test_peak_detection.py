"""Tests for libs/engagement/peak_detection.py."""

import pytest

from libs.engagement.peak_detection import find_extrema


pytestmark = pytest.mark.unit


def test_basic_top_n():
    series = [(0.0, 1), (60.0, 5), (120.0, 3), (180.0, 9), (240.0, 2), (300.0, 7)]
    peaks, valleys = find_extrema(series, n=3, min_spacing_sec=30.0)

    assert [p.score for p in peaks] == [9, 7, 5]
    assert [p.timestamp_sec for p in peaks] == [180.0, 300.0, 60.0]
    assert [p.rank for p in peaks] == [1, 2, 3]
    assert [v.score for v in valleys] == [1, 2, 3]


def test_min_spacing_enforced():
    # Three near-equal high values clustered together: spacing should pick only one
    series = [
        (0.0, 1),
        (10.0, 9),
        (15.0, 9),  # within spacing of (10, 9)
        (20.0, 9),  # within spacing of (10, 9)
        (200.0, 8),
        (400.0, 7),
    ]
    peaks, _ = find_extrema(series, n=3, min_spacing_sec=30.0)

    assert len(peaks) == 3
    times = sorted([p.timestamp_sec for p in peaks])
    # Adjacent picks must be at least 30s apart
    for a, b in zip(times, times[1:]):
        assert b - a >= 30.0


def test_fewer_points_than_n():
    series = [(0.0, 5), (100.0, 3)]
    peaks, valleys = find_extrema(series, n=5, min_spacing_sec=30.0)
    assert len(peaks) == 2
    assert len(valleys) == 2


def test_empty_series():
    peaks, valleys = find_extrema([], n=3)
    assert peaks == []
    assert valleys == []


def test_flat_series():
    series = [(t, 5.0) for t in range(0, 600, 30)]
    peaks, valleys = find_extrema(series, n=3, min_spacing_sec=30.0)
    # All scores equal — peaks and valleys both pick something, with spacing
    assert len(peaks) == 3
    times = sorted([p.timestamp_sec for p in peaks])
    for a, b in zip(times, times[1:]):
        assert b - a >= 30.0
