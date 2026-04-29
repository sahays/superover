"""Peak/valley detection for engagement timeseries."""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Extremum:
    """A single peak or valley point."""

    rank: int  # 1-indexed; rank 1 is the strongest
    timestamp_sec: float
    score: float


def _select_with_spacing(
    candidates: List[Tuple[float, float]],  # (score, time) presorted by score desc/asc
    n: int,
    min_spacing_sec: float,
) -> List[Tuple[float, float]]:
    """Greedy selection: walk best→worst, accept only if spaced from prior picks."""
    picked: List[Tuple[float, float]] = []
    for score, t in candidates:
        if all(abs(t - pt) >= min_spacing_sec for _, pt in picked):
            picked.append((score, t))
            if len(picked) >= n:
                break
    return picked


def find_extrema(
    series: List[Tuple[float, float]],
    n: int = 3,
    min_spacing_sec: float = 30.0,
) -> Tuple[List[Extremum], List[Extremum]]:
    """Return (peaks, valleys) — top-N highest and top-N lowest with min spacing.

    series: list of (timestamp_sec, score), assumed sorted by timestamp.
    n: number of peaks and valleys to return.
    min_spacing_sec: minimum seconds between selected extrema (within peaks or within valleys).
    """
    if not series:
        return [], []

    by_score_desc = sorted(((s, t) for t, s in series), key=lambda x: -x[0])
    by_score_asc = sorted(((s, t) for t, s in series), key=lambda x: x[0])

    peak_picks = _select_with_spacing(by_score_desc, n, min_spacing_sec)
    valley_picks = _select_with_spacing(by_score_asc, n, min_spacing_sec)

    peaks = [Extremum(rank=i + 1, timestamp_sec=t, score=s) for i, (s, t) in enumerate(peak_picks)]
    valleys = [Extremum(rank=i + 1, timestamp_sec=t, score=s) for i, (s, t) in enumerate(valley_picks)]
    return peaks, valleys
