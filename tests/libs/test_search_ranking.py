"""Unit tests for libs/search_ranking.py — deterministic recommendation ranking."""

import pytest

from libs.search_ranking import (
    CONFIDENCE_FLOOR,
    _confidence,
    _prettify_filename,
    _reason,
    rank_results,
)

MAX_DISTANCE = 1.05


def _row(video_id: str, distance: float, **overrides) -> dict:
    base = {
        "video_id": video_id,
        "video_filename": f"{video_id}.mp4",
        "gcs_path": f"gs://bucket/{video_id}.mp4",
        "distance": distance,
        "timestamp_start": None,
        "timestamp_end": None,
    }
    base.update(overrides)
    return base


@pytest.mark.unit
class TestRankResults:
    def test_orders_by_distance_and_caps_at_limit(self):
        groups = {f"v{i}": [_row(f"v{i}", 1.0 - i * 0.01)] for i in range(8)}
        recs = rank_results(groups, {}, max_distance=MAX_DISTANCE)
        assert len(recs) == 5
        assert [r["video_id"] for r in recs] == ["v7", "v6", "v5", "v4", "v3"]

    def test_display_threshold_gates_off_topic_rows(self):
        # Chitchat queries return rows, but all far — no cards (the filtering
        # the curator LLM used to do).
        groups = {
            "far1": [_row("far1", 1.09)],
            "far2": [_row("far2", 1.20)],
        }
        assert rank_results(groups, {}, max_distance=MAX_DISTANCE) == []

    def test_mixed_distances_keep_only_close_rows(self):
        groups = {
            "close": [_row("close", 0.97)],
            "far": [_row("far", 1.06)],
        }
        recs = rank_results(groups, {}, max_distance=MAX_DISTANCE)
        assert [r["video_id"] for r in recs] == ["close"]

    def test_uses_best_chunk_per_video(self):
        # Rows within a group are distance-ascending; the first is the best.
        groups = {
            "v1": [
                _row("v1", 0.96, timestamp_start="00:01:00", timestamp_end="00:01:30"),
                _row("v1", 1.01, timestamp_start="00:05:00", timestamp_end="00:05:30"),
            ]
        }
        recs = rank_results(groups, {}, max_distance=MAX_DISTANCE)
        assert recs[0]["clip_start"] == "00:01:00"
        assert recs[0]["clip_end"] == "00:01:30"

    def test_clip_when_chunk_has_time_range(self):
        groups = {"v1": [_row("v1", 0.96, timestamp_start="00:00:07.200", timestamp_end="00:00:44.500")]}
        rec = rank_results(groups, {}, max_distance=MAX_DISTANCE)[0]
        assert rec["recommendation_type"] == "clip"
        assert rec["clip_start"] == "00:00:07"  # millis dropped
        assert rec["clip_end"] == "00:00:44"

    def test_full_video_when_no_timestamps(self):
        rec = rank_results({"v1": [_row("v1", 0.96)]}, {}, max_distance=MAX_DISTANCE)[0]
        assert rec["recommendation_type"] == "full_video"
        assert rec["clip_start"] is None
        assert rec["clip_end"] is None

    def test_full_video_when_start_equals_end(self):
        groups = {"v1": [_row("v1", 0.96, timestamp_start="00:00:00", timestamp_end="00:00:00")]}
        rec = rank_results(groups, {}, max_distance=MAX_DISTANCE)[0]
        assert rec["recommendation_type"] == "full_video"

    def test_identifiers_and_confidence_populated(self):
        rec = rank_results({"v1": [_row("v1", 0.96)]}, {}, max_distance=MAX_DISTANCE)[0]
        assert rec["video_filename"] == "v1.mp4"
        assert rec["gcs_path"] == "gs://bucket/v1.mp4"
        assert rec["title"] == "v1"
        assert 0.0 <= rec["confidence"] <= 1.0

    def test_reason_from_metadata(self):
        meta = {"v1": {"genre": "Drama", "mood": "tense", "actors": ["A", "B", "C", "D"]}}
        rec = rank_results({"v1": [_row("v1", 0.96)]}, meta, max_distance=MAX_DISTANCE)[0]
        assert rec["reason"] == "Drama; tense; with A, B, C"

    def test_row_without_distance_is_skipped(self):
        row = _row("v1", 0.96)
        del row["distance"]
        assert rank_results({"v1": [row]}, {}, max_distance=MAX_DISTANCE) == []

    def test_empty_groups(self):
        assert rank_results({}, {}, max_distance=MAX_DISTANCE) == []


@pytest.mark.unit
class TestHelpers:
    def test_confidence_ramp(self):
        at_threshold = _confidence(MAX_DISTANCE, MAX_DISTANCE)
        tight = _confidence(MAX_DISTANCE - 0.25, MAX_DISTANCE)
        assert at_threshold == CONFIDENCE_FLOOR
        assert tight == 1.0
        assert _confidence(0.0, MAX_DISTANCE) == 1.0  # clamped

    def test_prettify_filename(self):
        assert _prettify_filename("Sony_Liv-The_Hunt.mp4") == "Sony Liv The Hunt"
        assert _prettify_filename("dir/clip name.mov") == "clip name"
        assert _prettify_filename(None) == "Untitled"
        assert _prettify_filename("...") == "Untitled"

    def test_reason_fallbacks(self):
        assert _reason({"description": "x" * 200}).startswith("x")
        assert len(_reason({"description": "x" * 200})) == 120
        assert _reason({}) == "Close semantic match"
