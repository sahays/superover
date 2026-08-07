"""End-to-end test for UnifiedWorker._process_engagement_job (mocked clients)."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.worker


@pytest.fixture
def worker():
    """Build a UnifiedWorker with all external clients mocked."""
    from libs.engagement.peak_detection import Extremum
    from libs.engagement.scene_context import ChunkContext

    # Heavy imports patched so __init__ doesn't try to talk to GCP
    with (
        patch("workers.unified_worker.get_db") as gd,
        patch("workers.unified_worker.get_storage") as gs,
        patch("workers.unified_worker.get_transcoder_client") as gt,
        patch("workers.unified_worker.get_scene_analyzer") as gsa,
        patch("workers.unified_worker.get_image_analyzer") as gia,
        patch("workers.unified_worker.get_engagement_analyzer") as gea,
        patch("workers.unified_worker.get_scene_processor"),
        patch("workers.unified_worker.SceneOrchestrator"),
    ):
        from workers.unified_worker import UnifiedWorker

        db = MagicMock()
        storage = MagicMock()
        engagement = MagicMock()
        gd.return_value = db
        gs.return_value = storage
        gt.return_value = MagicMock()
        gsa.return_value = MagicMock()
        gia.return_value = MagicMock()
        gea.return_value = engagement

        w = UnifiedWorker()
        w._db = db
        w._storage = storage
        w._engagement = engagement
        w._Extremum = Extremum
        w._ChunkContext = ChunkContext
        return w


def _make_csv() -> bytes:
    rows = ["timestamp,engagement"]
    # 0..200s at 10s spacing — 21 points. Build a clear peak at 100, valley at 30.
    scores = {
        0: 5,
        10: 5,
        20: 4,
        30: 1,
        40: 4,
        50: 5,
        60: 5,
        70: 6,
        80: 7,
        90: 8,
        100: 9,
        110: 8,
        120: 7,
        130: 6,
        140: 5,
        150: 5,
        160: 5,
        170: 4,
        180: 5,
        190: 5,
        200: 5,
    }
    for t, s in scores.items():
        rows.append(f"{t},{s}")
    return "\n".join(rows).encode("utf-8")


def test_process_engagement_job_happy_path(worker):
    """Full path: parse BARC → detect extrema → fetch context → call Gemini → write results."""
    from libs.db.enums import EngagementJobStatus

    db = worker._db
    storage = worker._storage
    engagement = worker._engagement

    # Storage parse_gcs_path + blob.download_as_bytes()
    storage._parse_gcs_path.return_value = ("uploads-bucket", "engagement/x.csv")
    blob = MagicMock()
    blob.download_as_bytes.return_value = _make_csv()
    storage.client.bucket.return_value.blob.return_value = blob
    storage.upload_bytes = MagicMock()

    # Source scene job + manifest + per-chunk results for fetch_chunks_at
    db.get_scene_job.return_value = {"job_id": "src-1", "video_id": "v1"}
    db.get_manifest.return_value = {
        "video_id": "v1",
        "chunks": [
            {"index": 0, "start_time": 0.0, "end_time": 60.0},
            {"index": 1, "start_time": 60.0, "end_time": 120.0},
            {"index": 2, "start_time": 120.0, "end_time": 200.0},
        ],
    }
    db.get_results_for_job.return_value = [
        {"scene_job_id": "src-1", "result_data": {"chunk_index": 0, "raw_text": "intro scene"}},
        {"scene_job_id": "src-1", "result_data": {"chunk_index": 1, "raw_text": "fight scene"}},
        {"scene_job_id": "src-1", "result_data": {"chunk_index": 2, "raw_text": "outro scene"}},
    ]

    # Gemini engagement analyzer returns structured response
    engagement.explain.return_value = {
        "peaks": [
            {
                "rank": 1,
                "timestamp_sec": 100.0,
                "scene_summary": "fight peak",
                "explanation": "punch lands",
                "key_actors": ["hero"],
                "key_events": ["punch"],
                "key_objects": [],
            },
            {"rank": 2, "timestamp_sec": 80.0, "scene_summary": "build", "explanation": "tension rises"},
            {"rank": 3, "timestamp_sec": 70.0, "scene_summary": "build", "explanation": "tension rises"},
        ],
        "valleys": [
            {
                "rank": 1,
                "timestamp_sec": 30.0,
                "scene_summary": "lull",
                "explanation": "exposition",
                "key_actors": [],
                "key_events": [],
                "key_objects": [],
            },
            {"rank": 2, "timestamp_sec": 170.0, "scene_summary": "outro", "explanation": "winding down"},
            {"rank": 3, "timestamp_sec": 20.0, "scene_summary": "intro", "explanation": "slow start"},
        ],
        "finish_reason": "STOP",
        "token_usage": {"prompt_tokens": 1, "candidates_tokens": 2, "total_tokens": 3, "estimated_cost_usd": 0.0001},
    }
    engagement.summarize_episode.return_value = {
        "summary": "Epic match summary",
        "token_usage": {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
    }
    engagement.recommend.return_value = {
        "headline": "Lean into Hero scenes; trim slow exposition.",
        "do_more_of": [
            {
                "recommendation": "More Hero",
                "rationale": "+45%",
                "expected_lift": "high",
                "evidence": {"entity": "Hero"},
            }
        ],
        "do_less_of": [],
        "per_minute_callouts": [],
        "finish_reason": "STOP",
        "token_usage": {"prompt_tokens": 1, "candidates_tokens": 1, "total_tokens": 2, "estimated_cost_usd": 0.00005},
    }

    job = {
        "job_id": "eng-1",
        "video_id": "v1",
        "source_scene_job_id": "src-1",
        "barc_gcs_path": "gs://uploads-bucket/engagement/x.csv",
        "config": None,
    }

    worker._process_engagement_job(job)

    # 1. Status transitions
    statuses = [c.args[1] for c in db.update_engagement_job_status.call_args_list]
    assert EngagementJobStatus.PROCESSING in statuses
    assert EngagementJobStatus.COMPLETED in statuses

    # 2. Last status update wrote merged results (peaks/valleys + timeseries path)
    final_call = db.update_engagement_job_status.call_args_list[-1]
    final_kwargs = final_call.kwargs
    results = final_kwargs["results"]
    assert len(results["peaks"]) == 3
    assert len(results["valleys"]) == 3
    assert results["peaks"][0]["rank"] == 1
    assert results["peaks"][0]["explanation"] == "punch lands"
    assert results["peaks"][0]["chunk_index"] == 1  # 100s falls in chunk 1
    assert results["valleys"][0]["chunk_index"] == 0  # 30s falls in chunk 0
    assert results["timeseries_gcs_path"].startswith("gs://")
    assert results["cues_gcs_path"].startswith("gs://")
    assert results["entities_gcs_path"].startswith("gs://")
    assert results["recommendations_gcs_path"].startswith("gs://")
    assert results["barc_time_column"] == "timestamp"
    assert results["barc_score_column"] == "engagement"
    assert results["point_count"] == 21
    assert results["finish_reason"] == "STOP"
    # Token usage aggregates explain + recommend
    assert results["token_usage"]["total_tokens"] == 5  # 3 + 2

    # 3. Four GCS uploads happened (timeseries, cues, entities, recommendations)
    upload_paths = [c.args[1] for c in storage.upload_bytes.call_args_list]
    assert any(p.endswith("timeseries.json") for p in upload_paths)
    assert any(p.endswith("cues.json") for p in upload_paths)
    assert any(p.endswith("entities.json") for p in upload_paths)
    assert any(p.endswith("recommendations.json") for p in upload_paths)

    # 4. Engagement analyzer received 3 peaks + 3 valleys with their contexts
    assert engagement.explain.called
    call_kwargs = engagement.explain.call_args.kwargs
    assert len(call_kwargs["peaks"]) == 3
    assert len(call_kwargs["valleys"]) == 3
    assert set(call_kwargs["contexts"].keys()) == {p.timestamp_sec for p in call_kwargs["peaks"]} | {
        v.timestamp_sec for v in call_kwargs["valleys"]
    }

    # 5. Recommendations call was made with stats + cues_by_minute
    assert engagement.recommend.called
    rec_args = engagement.recommend.call_args
    stats_arg = rec_args.args[0] if rec_args.args else rec_args.kwargs.get("stats")
    assert stats_arg is not None
    assert hasattr(stats_arg, "overall_avg")


def test_process_engagement_job_raises_on_bad_barc(worker):
    """Malformed BARC → raises (top-level handler in pending-jobs marks FAILED)."""
    storage = worker._storage
    storage._parse_gcs_path.return_value = ("uploads", "x.csv")
    blob = MagicMock()
    blob.download_as_bytes.return_value = b"foo,bar\n1,2\n"  # no time/score columns
    storage.client.bucket.return_value.blob.return_value = blob

    job = {
        "job_id": "eng-1",
        "video_id": "v1",
        "source_scene_job_id": "src-1",
        "barc_gcs_path": "gs://uploads/x.csv",
        "config": None,
    }

    with pytest.raises(ValueError):
        worker._process_engagement_job(job)


def test_process_pending_engagement_marks_failed_on_error(worker):
    """If _process_engagement_job throws, the outer poller marks the job FAILED."""
    from libs.db.enums import EngagementJobStatus

    db = worker._db
    db.get_pending_engagement_jobs.return_value = [
        {
            "job_id": "eng-1",
            "video_id": "v1",
            "source_scene_job_id": "src-1",
            "barc_gcs_path": "gs://x/y.csv",
            "config": None,
        }
    ]

    with patch.object(worker, "_process_engagement_job", side_effect=RuntimeError("boom")):
        worker._process_pending_engagement_jobs()

    # Should have called update_engagement_job_status with FAILED
    failed_calls = [c for c in db.update_engagement_job_status.call_args_list if EngagementJobStatus.FAILED in c.args]
    assert failed_calls, "Expected FAILED status update on processing error"
    assert "boom" in (failed_calls[-1].kwargs.get("error_message") or "")
