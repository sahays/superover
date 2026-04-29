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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

    points: List[Tuple[float, float]]  # primary metric: (seconds_from_start, score)
    time_column: str
    score_column: str
    anchor_offset_sec: float = 0.0  # raw seconds subtracted to make first row t=0
    # Every numeric column from the CSV (including the primary), keyed by the
    # original header. Anchored the same way as `points`.
    metrics: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)

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
    raise ValueError(f"could not find a {label} column in headers {headers}; expected one of {candidates}")


def parse_barc_csv(data: bytes) -> BarcSeries:
    """Parse BARC CSV bytes into a sorted (sec, score) series.

    Auto-anchors clock-time columns (e.g. "20:00:00") so the first row becomes
    t=0 and subsequent rows are seconds from start. Collects every numeric
    column the CSV exposes (TVR, Impressions, Reach, ...) into `metrics`.
    """
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        raise ValueError("BARC CSV has no header row")

    rows = list(reader)
    if not rows:
        raise ValueError("BARC CSV has no data rows")

    time_col = _resolve_column(headers, TIME_COLUMN_CANDIDATES, "time")
    score_col = _resolve_column(headers, SCORE_COLUMN_CANDIDATES, "score")
    numeric_cols = _detect_numeric_columns(headers, rows, exclude={time_col})
    # Score column was resolved by name match; ensure it's always treated as
    # numeric even if its sample values happen to be malformed.
    if score_col not in numeric_cols:
        numeric_cols.insert(0, score_col)

    # Build raw points keyed by absolute timestamp, then anchor at the end.
    raw_by_col: Dict[str, List[Tuple[float, float]]] = {col: [] for col in numeric_cols}
    skipped = 0
    for row in rows:
        try:
            t = _parse_timestamp(row[time_col])
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue
        if not math.isfinite(t):
            skipped += 1
            continue
        for col in numeric_cols:
            s = _parse_score(row.get(col))
            if s is not None and math.isfinite(s):
                raw_by_col[col].append((t, s))

    if not raw_by_col[score_col]:
        raise ValueError("BARC CSV produced zero valid rows for the primary score column")

    # Sort each metric by time. All metrics share the same anchor (derived from
    # the primary score's first timestamp) so they line up in chart overlays.
    for col in raw_by_col:
        raw_by_col[col].sort(key=lambda p: p[0])

    primary_first_ts = raw_by_col[score_col][0][0]
    anchor = primary_first_ts if primary_first_ts >= 60 else 0.0

    metrics = {col: [(t - anchor, s) for t, s in series] for col, series in raw_by_col.items() if series}

    if skipped:
        logger.warning(f"BARC parser skipped {skipped} malformed row(s)")
    if anchor:
        logger.info(f"BARC parser anchored series at {anchor}s (column: {time_col})")
    logger.info(f"BARC parser detected metrics: {list(metrics.keys())} (primary={score_col})")

    return BarcSeries(
        points=metrics[score_col],
        time_column=time_col,
        score_column=score_col,
        anchor_offset_sec=anchor,
        metrics=metrics,
    )


def _detect_numeric_columns(headers: List[str], rows: List[dict], exclude: set, sample_size: int = 5) -> List[str]:
    """Return columns whose values parse as numbers in the first `sample_size` rows.

    Order: primary score column candidates first (in candidate priority), then
    any remaining numeric columns alphabetically. The caller injects `exclude`
    for the time column so it never makes the metrics list.
    """
    sample = rows[:sample_size]
    numeric: List[str] = []
    for col in headers:
        if col in exclude:
            continue
        parses = sum(1 for r in sample if _parse_score(r.get(col)) is not None)
        if parses >= max(1, len(sample) // 2):  # majority must parse
            numeric.append(col)

    # Reorder by SCORE_COLUMN_CANDIDATES priority, then alphabetical for the rest.
    norm_to_orig = {_normalize_header(h): h for h in numeric}
    ordered: List[str] = []
    for candidate in SCORE_COLUMN_CANDIDATES:
        if candidate in norm_to_orig and norm_to_orig[candidate] not in ordered:
            ordered.append(norm_to_orig[candidate])
        # Substring fallback (e.g. "tvr" matches "tvr ")
        for norm, orig in norm_to_orig.items():
            if candidate in norm.split() and orig not in ordered:
                ordered.append(orig)

    for col in sorted(numeric):
        if col not in ordered:
            ordered.append(col)
    return ordered


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
