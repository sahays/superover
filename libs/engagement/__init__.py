"""Engagement analysis: BARC parsing, peak detection, scene context lookup."""

from .barc_parser import parse_barc_csv, BarcSeries
from .peak_detection import find_extrema, Extremum
from .scene_context import fetch_chunks_at, ChunkContext

__all__ = [
    "parse_barc_csv",
    "BarcSeries",
    "find_extrema",
    "Extremum",
    "fetch_chunks_at",
    "ChunkContext",
]
