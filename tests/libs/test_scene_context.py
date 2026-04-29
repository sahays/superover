"""Tests for libs/engagement/scene_context.py."""

from unittest.mock import MagicMock

import pytest

from libs.engagement.scene_context import fetch_chunks_at


pytestmark = pytest.mark.unit


def _make_db(scene_job=None, manifest=None, results=None):
    db = MagicMock()
    db.get_scene_job.return_value = scene_job
    db.get_manifest.return_value = manifest
    db.get_results_for_job.return_value = results or []
    return db


def test_finds_chunk_for_timestamp_in_range():
    job = {"job_id": "j1", "video_id": "v1"}
    manifest = {
        "video_id": "v1",
        "chunks": [
            {"index": 0, "start_time": 0.0, "end_time": 30.0, "duration": 30},
            {"index": 1, "start_time": 30.0, "end_time": 60.0, "duration": 30},
            {"index": 2, "start_time": 60.0, "end_time": 90.0, "duration": 30},
        ],
    }
    results = [
        {"scene_job_id": "j1", "result_data": {"chunk_index": 1, "raw_text": "fight scene"}},
    ]
    db = _make_db(job, manifest, results)

    out = fetch_chunks_at(db, "j1", [45.0])

    assert out[45.0].chunk_index == 1
    assert out[45.0].raw_text == "fight scene"
    assert out[45.0].start_time == 30.0
    assert out[45.0].end_time == 60.0


def test_chunk_boundary_belongs_to_next_chunk():
    job = {"job_id": "j1", "video_id": "v1"}
    manifest = {
        "chunks": [
            {"index": 0, "start_time": 0.0, "end_time": 30.0},
            {"index": 1, "start_time": 30.0, "end_time": 60.0},
        ],
    }
    db = _make_db(job, manifest, [])

    out = fetch_chunks_at(db, "j1", [30.0])
    assert out[30.0].chunk_index == 1


def test_timestamp_past_last_chunk_clamps_to_last():
    job = {"job_id": "j1", "video_id": "v1"}
    manifest = {
        "chunks": [
            {"index": 0, "start_time": 0.0, "end_time": 30.0},
            {"index": 1, "start_time": 30.0, "end_time": 60.0},
        ],
    }
    db = _make_db(job, manifest, [])

    out = fetch_chunks_at(db, "j1", [120.0])
    assert out[120.0].chunk_index == 1


def test_single_chunk_fallback_covers_everything():
    """When chunking is disabled, the manifest has a single chunk with no time bounds."""
    job = {"job_id": "j1", "video_id": "v1"}
    manifest = {
        "chunks": [
            {"index": 0, "filename": "video.mp4", "duration": 0},
        ],
    }
    db = _make_db(job, manifest, [])

    out = fetch_chunks_at(db, "j1", [0.0, 999.0])
    assert out[0.0].chunk_index == 0
    assert out[999.0].chunk_index == 0


def test_unknown_scene_job_raises():
    db = _make_db(scene_job=None)
    with pytest.raises(ValueError, match="Scene job not found"):
        fetch_chunks_at(db, "missing", [0.0])
