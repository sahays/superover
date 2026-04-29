"""BARC CSV parser — normalizes (timestamp, score) rows to a sorted float series.

Handles two shapes:

  1. Simple per-row timeseries with explicit time + score columns
     (timestamp / time / t / seconds, plus engagement / score / value / rating).

  2. Real BARC reports with `Start Time` / `End Time` (clock time) and
     `TVR (%)` / `Impressions ('000s)` / `Reach ('000s)` columns. Times are
     auto-anchored so the first row maps to t=0 (subtracting the minimum).
"""

import csv
import io
import logging
import math
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Header candidates are matched against normalized header text:
# lowercased, non-alphanumerics collapsed to single spaces, trimmed.
TIME_COLUMN_CANDIDATES: tuple = (
    "start time",
    "starttime",
    "start_time",
    "timestamp",
    "time",
    "t",
    "seconds",
    "sec",
    "secs",
)

# Priority order: prefer TVR (the standard BARC engagement metric), then other
# rating/score signals, then raw audience counts.
SCORE_COLUMN_CANDIDATES: tuple = (
    "tvr",
    "engagement",
    "score",
    "rating",
    "value",
    "impressions 000s",
    "impressions",
    "reach 000s",
    "reach",
    "viewers",
)


@dataclass
class BarcSeries:
    """Parsed BARC engagement series."""

    points: List[Tuple[float, float]]  # (seconds_from_start, score)
    time_column: str
    score_column: str
    anchor_offset_sec: float = 0.0  # raw seconds subtracted to make first row t=0

    @property
    def duration_sec(self) -> float:
        return self.points[-1][0] if self.points else 0.0


def _normalize_header(name: str) -> str:
    """Lowercase, strip punctuation/parentheses, collapse whitespace."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _parse_timestamp(value: str) -> float:
    """Convert a timestamp cell to float seconds.

    Accepts plain numbers ("12.5", "300") or hh:mm:ss[.ms] / mm:ss formats.
    """
    s = value.strip()
    if not s:
        raise ValueError("empty timestamp")

    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2:  # mm:ss
            mm, ss = parts
            return int(mm) * 60 + float(ss)
        if len(parts) == 3:  # hh:mm:ss
            hh, mm, ss = parts
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
        raise ValueError(f"unrecognized time format: {value}")

    return float(s)


def _resolve_column(headers: List[str], candidates: tuple, label: str) -> str:
    """Pick the original-cased header matching the first candidate found."""
    norm_to_orig = {_normalize_header(h): h for h in headers}
    for candidate in candidates:
        if candidate in norm_to_orig:
            return norm_to_orig[candidate]
    # Fall back to substring match (e.g. "TVR (%)" → "tvr" inside "tvr ")
    for candidate in candidates:
        for norm, orig in norm_to_orig.items():
            if candidate in norm.split():
                return orig
    raise ValueError(
        f"could not find a {label} column in headers {headers}; "
        f"expected one of {candidates}"
    )


def parse_barc_csv(data: bytes) -> BarcSeries:
    """Parse BARC CSV bytes into a sorted (sec, score) series.

    Auto-anchors clock-time columns (e.g. "20:00:00") so the first row becomes
    t=0 and subsequent rows are seconds from start.
    """
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        raise ValueError("BARC CSV has no header row")

    time_col = _resolve_column(headers, TIME_COLUMN_CANDIDATES, "time")
    score_col = _resolve_column(headers, SCORE_COLUMN_CANDIDATES, "score")

    raw: List[Tuple[float, float]] = []
    skipped = 0
    for row in reader:
        try:
            t = _parse_timestamp(row[time_col])
            s = _parse_score(row[score_col])
            if s is None or not (math.isfinite(t) and math.isfinite(s)):
                skipped += 1
                continue
            raw.append((t, s))
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue

    if not raw:
        raise ValueError("BARC CSV produced zero valid rows")

    raw.sort(key=lambda p: p[0])

    # Auto-anchor: if the smallest timestamp is far above zero (typical clock
    # times like 20:00:00 = 72000s), subtract the minimum so the series is
    # zero-based and aligned with the start of the video.
    anchor = raw[0][0] if raw[0][0] >= 60 else 0.0
    points = [(t - anchor, s) for t, s in raw]

    if skipped:
        logger.warning(f"BARC parser skipped {skipped} malformed row(s)")
    if anchor:
        logger.info(f"BARC parser anchored series at {anchor}s (column: {time_col})")

    return BarcSeries(
        points=points,
        time_column=time_col,
        score_column=score_col,
        anchor_offset_sec=anchor,
    )


def _parse_score(value: str) -> Optional[float]:
    """Parse a score cell. Strips %, commas, and quoted thousands separators."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("%", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
