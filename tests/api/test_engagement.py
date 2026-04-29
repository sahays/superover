"""API tests for engagement analysis endpoints."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-Invite-Code": "TEST-MASTER"}


@pytest.fixture
def mock_db_and_auth():
    """Patch get_db in the engagement route + bypass invite-code middleware."""
    with (
        patch("api.routes.engagement.get_db") as mock_get_db,
        patch("api.routes.auth.validate_code") as mock_validate,
    ):
        db = MagicMock()
        mock_get_db.return_value = db
        mock_validate.return_value = {"valid": True, "is_master": True}
        yield db


def test_signed_url_route(client, auth_headers, mock_db_and_auth):
    """POST /api/engagement/signed-url returns a signed URL + GCS path."""
    with patch("api.routes.engagement.get_storage") as mock_get_storage:
        storage = MagicMock()
        storage.generate_signed_upload_url.return_value = (
            "https://signed.example/upload",
            "gs://uploads/engagement/abc.csv",
        )
        mock_get_storage.return_value = storage

        resp = client.post(
            "/api/engagement/signed-url",
            json={"filename": "barc.csv", "content_type": "text/csv"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["signed_url"].startswith("https://")
    assert body["gcs_path"].startswith("gs://uploads/engagement/")
    # Filename in storage call should be unique-ified under engagement/
    args, kwargs = storage.generate_signed_upload_url.call_args
    assert kwargs["filename"].startswith("engagement/")
    assert kwargs["filename"].endswith(".csv")
    assert kwargs["bucket_type"] == "uploads"


def test_list_all_eligible_uses_status_only_query(client, auth_headers, mock_db_and_auth):
    """Regression: GET /api/engagement/scene-jobs must NOT use a (status, created_at)
    composite query (which would 400 in Firestore without an index). It must do a
    simple where(status==completed) and sort in Python.
    """
    db = mock_db_and_auth
    where_chain = MagicMock()
    db.scene_jobs.where.return_value = where_chain
    where_chain.limit.return_value = where_chain
    where_chain.stream.return_value = [
        _doc({"job_id": "j2", "video_id": "v1", "prompt_name": "Old", "created_at": _ts("2026-04-01")}),
        _doc({"job_id": "j1", "video_id": "v1", "prompt_name": "New", "created_at": _ts("2026-04-20")}),
    ]

    resp = client.get("/api/engagement/scene-jobs?limit=50", headers=auth_headers)

    assert resp.status_code == 200, resp.text

    # Verify only a single where() call (status filter), no order_by.
    db.scene_jobs.where.assert_called_once()
    where_args = db.scene_jobs.where.call_args
    # Field name "status" must be the where filter
    assert "status" in where_args.args or where_args.kwargs.get("field") == "status" or where_args.args[0] == "status"
    # No order_by anywhere on the chain (would require a composite index)
    assert not where_chain.order_by.called

    # Results sorted newest-first by created_at
    items = resp.json()
    assert [j["job_id"] for j in items] == ["j1", "j2"]
    # And paginated repo helper was NOT used (it triggers the index bug)
    assert not db.list_scene_jobs_paginated.called


def test_list_all_eligible_returns_all_prompt_types(client, auth_headers, mock_db_and_auth):
    """Filter must NOT exclude prompt types other than 'scene_analysis'."""
    db = mock_db_and_auth
    where_chain = MagicMock()
    db.scene_jobs.where.return_value = where_chain
    where_chain.limit.return_value = where_chain
    where_chain.stream.return_value = [
        _doc({"job_id": "j1", "video_id": "v1", "prompt_type": "scene_analysis", "prompt_name": "Scene"}),
        _doc({"job_id": "j2", "video_id": "v1", "prompt_type": "custom", "prompt_name": "Custom"}),
        _doc({"job_id": "j3", "video_id": "v1", "prompt_type": "subtitling", "prompt_name": "Subs"}),
    ]

    resp = client.get("/api/engagement/scene-jobs", headers=auth_headers)

    assert resp.status_code == 200
    ids = sorted(j["job_id"] for j in resp.json())
    assert ids == ["j1", "j2", "j3"]


def test_list_engagement_jobs_for_video_uses_no_order_by(client, auth_headers, mock_db_and_auth):
    """Regression: GET /api/engagement/videos/{id}/jobs must NOT issue
    where(video_id) + order_by(created_at) — that needs a composite index.
    The repo method should query with where() only and sort in Python.
    """
    db = mock_db_and_auth
    where_chain = MagicMock()
    db.engagement_jobs.where.return_value = where_chain
    where_chain.stream.return_value = [
        _doc(
            {
                "job_id": "e2",
                "video_id": "v1",
                "source_scene_job_id": "s",
                "barc_gcs_path": "gs://x",
                "status": "completed",
                "created_at": _ts("2026-04-01"),
            }
        ),
        _doc(
            {
                "job_id": "e1",
                "video_id": "v1",
                "source_scene_job_id": "s",
                "barc_gcs_path": "gs://x",
                "status": "completed",
                "created_at": _ts("2026-04-20"),
            }
        ),
    ]
    # Force the route to use the real db.list_engagement_jobs_for_video
    from libs.db.engagement import EngagementMixin

    db.list_engagement_jobs_for_video = EngagementMixin.list_engagement_jobs_for_video.__get__(db)

    resp = client.get("/api/engagement/videos/v1/jobs", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    # Single where() — no order_by, otherwise Firestore demands a composite index.
    assert db.engagement_jobs.where.called
    assert not where_chain.order_by.called
    # And results come out newest-first (sorted in Python)
    assert [j["job_id"] for j in resp.json()] == ["e1", "e2"]


def test_list_eligible_for_video(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.list_scene_jobs_for_video.return_value = [
        {"job_id": "j1", "video_id": "v1", "prompt_name": "S", "prompt_type": "scene_analysis"},
    ]

    resp = client.get("/api/engagement/videos/v1/scene-jobs", headers=auth_headers)

    assert resp.status_code == 200
    assert [j["job_id"] for j in resp.json()] == ["j1"]
    db.list_scene_jobs_for_video.assert_called_once()


def test_create_job_404_when_video_missing(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_video.return_value = None

    resp = client.post(
        "/api/engagement/jobs",
        json={
            "video_id": "v-missing",
            "source_scene_job_id": "j1",
            "barc_gcs_path": "gs://uploads/engagement/x.csv",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 404
    assert "Video not found" in resp.text


def test_create_job_400_when_source_job_video_mismatch(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_video.return_value = {"video_id": "v1"}
    db.get_scene_job.return_value = {"job_id": "j1", "video_id": "v-other", "status": "completed"}

    resp = client.post(
        "/api/engagement/jobs",
        json={
            "video_id": "v1",
            "source_scene_job_id": "j1",
            "barc_gcs_path": "gs://uploads/engagement/x.csv",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_job_400_when_source_job_not_completed(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_video.return_value = {"video_id": "v1"}
    db.get_scene_job.return_value = {"job_id": "j1", "video_id": "v1", "status": "processing"}

    resp = client.post(
        "/api/engagement/jobs",
        json={
            "video_id": "v1",
            "source_scene_job_id": "j1",
            "barc_gcs_path": "gs://uploads/engagement/x.csv",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 400
    assert "COMPLETED" in resp.text


def test_create_job_happy_path(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_video.return_value = {"video_id": "v1"}
    db.get_scene_job.return_value = {"job_id": "j1", "video_id": "v1", "status": "completed"}
    db.create_engagement_job.return_value = {
        "job_id": "eng-1",
        "video_id": "v1",
        "source_scene_job_id": "j1",
        "barc_gcs_path": "gs://uploads/engagement/x.csv",
        "status": "pending",
    }

    resp = client.post(
        "/api/engagement/jobs",
        json={
            "video_id": "v1",
            "source_scene_job_id": "j1",
            "barc_gcs_path": "gs://uploads/engagement/x.csv",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["job_id"] == "eng-1"
    db.create_engagement_job.assert_called_once()


def test_get_job_404(client, auth_headers, mock_db_and_auth):
    mock_db_and_auth.get_engagement_job.return_value = None
    resp = client.get("/api/engagement/jobs/missing", headers=auth_headers)
    assert resp.status_code == 404


def test_get_job_returns_results(client, auth_headers, mock_db_and_auth):
    mock_db_and_auth.get_engagement_job.return_value = {
        "job_id": "eng-1",
        "video_id": "v1",
        "source_scene_job_id": "j1",
        "barc_gcs_path": "gs://uploads/engagement/x.csv",
        "status": "completed",
        "results": {
            "peaks": [{"rank": 1, "timestamp_sec": 10.0, "score": 9.0}],
            "valleys": [{"rank": 1, "timestamp_sec": 60.0, "score": 1.0}],
            "point_count": 100,
        },
    }
    resp = client.get("/api/engagement/jobs/eng-1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["results"]["peaks"][0]["rank"] == 1


def test_auth_required(client, mock_db_and_auth):
    """No invite code → 401."""
    resp = client.get("/api/engagement/scene-jobs")
    assert resp.status_code == 401


def test_timeseries_returns_all_metrics(client, auth_headers, mock_db_and_auth):
    """Multi-metric: response carries `metrics` dict with every BARC column."""
    db = mock_db_and_auth
    db.get_engagement_job.return_value = {
        "job_id": "eng-1",
        "results": {"timeseries_gcs_path": "gs://results/engagement/eng-1/timeseries.json"},
    }
    payload = {
        "metrics": {
            "TVR (%)": [[0, 0.45], [60, 0.52]],
            "Impressions ('000s)": [[0, 350], [60, 420]],
        },
        "primary_metric": "TVR (%)",
        "time_column": "Start Time",
        "score_column": "TVR (%)",
    }
    _stub_blob(db, payload)

    with patch("api.routes.engagement.get_storage") as gs:
        storage = MagicMock()
        storage._parse_gcs_path.return_value = ("results", "engagement/eng-1/timeseries.json")
        blob = MagicMock()
        blob.download_as_bytes.return_value = _to_json(payload)
        storage.client.bucket.return_value.blob.return_value = blob
        gs.return_value = storage

        resp = client.get("/api/engagement/jobs/eng-1/timeseries", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "TVR (%)" in body["metrics"]
    assert "Impressions ('000s)" in body["metrics"]
    assert body["primary_metric"] == "TVR (%)"
    # `points` back-compat: returns the primary metric
    assert body["points"] == [[0, 0.45], [60, 0.52]]


def test_timeseries_back_compat_points_only(client, auth_headers, mock_db_and_auth):
    """Older jobs that stored `points` instead of `metrics` still work."""
    db = mock_db_and_auth
    db.get_engagement_job.return_value = {
        "job_id": "eng-old",
        "results": {"timeseries_gcs_path": "gs://results/engagement/eng-old/timeseries.json"},
    }
    payload = {"points": [[0, 1.0], [10, 2.0]], "score_column": "engagement"}

    with patch("api.routes.engagement.get_storage") as gs:
        storage = MagicMock()
        storage._parse_gcs_path.return_value = ("results", "engagement/eng-old/timeseries.json")
        blob = MagicMock()
        blob.download_as_bytes.return_value = _to_json(payload)
        storage.client.bucket.return_value.blob.return_value = blob
        gs.return_value = storage

        resp = client.get("/api/engagement/jobs/eng-old/timeseries", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    # Falls back to `points` when `metrics` is absent
    assert body["metrics"] == {"engagement": [[0, 1.0], [10, 2.0]]}
    assert body["points"] == [[0, 1.0], [10, 2.0]]


def test_entities_endpoint_returns_payload(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_engagement_job.return_value = {
        "job_id": "eng-1",
        "results": {"entities_gcs_path": "gs://results/engagement/eng-1/entities.json"},
    }
    payload = [
        {"name": "Hero", "kind": "character", "appearances": [], "mention_count": 5},
    ]
    with patch("api.routes.engagement.get_storage") as gs:
        storage = MagicMock()
        storage._parse_gcs_path.return_value = ("results", "engagement/eng-1/entities.json")
        blob = MagicMock()
        blob.download_as_bytes.return_value = _to_json(payload)
        storage.client.bucket.return_value.blob.return_value = blob
        gs.return_value = storage

        resp = client.get("/api/engagement/jobs/eng-1/entities", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Hero"


def test_cues_endpoint_returns_payload(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_engagement_job.return_value = {
        "job_id": "eng-1",
        "results": {"cues_gcs_path": "gs://results/engagement/eng-1/cues.json"},
    }
    payload = [{"start_sec": 1.0, "end_sec": 3.0, "text": "Hello", "kind": "dialogue", "speaker": "Hero"}]
    with patch("api.routes.engagement.get_storage") as gs:
        storage = MagicMock()
        storage._parse_gcs_path.return_value = ("results", "engagement/eng-1/cues.json")
        blob = MagicMock()
        blob.download_as_bytes.return_value = _to_json(payload)
        storage.client.bucket.return_value.blob.return_value = blob
        gs.return_value = storage

        resp = client.get("/api/engagement/jobs/eng-1/cues", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["speaker"] == "Hero"


def test_recommendations_endpoint_returns_payload(client, auth_headers, mock_db_and_auth):
    db = mock_db_and_auth
    db.get_engagement_job.return_value = {
        "job_id": "eng-1",
        "results": {"recommendations_gcs_path": "gs://results/engagement/eng-1/recommendations.json"},
    }
    payload = {
        "headline": "Lean into Hero scenes",
        "do_more_of": [],
        "do_less_of": [],
        "per_minute_callouts": [],
    }
    with patch("api.routes.engagement.get_storage") as gs:
        storage = MagicMock()
        storage._parse_gcs_path.return_value = ("results", "engagement/eng-1/recommendations.json")
        blob = MagicMock()
        blob.download_as_bytes.return_value = _to_json(payload)
        storage.client.bucket.return_value.blob.return_value = blob
        gs.return_value = storage

        resp = client.get("/api/engagement/jobs/eng-1/recommendations", headers=auth_headers)
    assert resp.status_code == 200
    assert "Hero" in resp.json()["headline"]


def test_artifact_404_when_path_missing(client, auth_headers, mock_db_and_auth):
    """If the engagement job exists but lacks the artifact path, return 404."""
    mock_db_and_auth.get_engagement_job.return_value = {
        "job_id": "eng-1",
        "results": {},  # no entities_gcs_path
    }
    resp = client.get("/api/engagement/jobs/eng-1/entities", headers=auth_headers)
    assert resp.status_code == 404


def _to_json(payload) -> bytes:
    import json as _json

    return _json.dumps(payload).encode("utf-8")


def _stub_blob(*_args, **_kwargs):
    """Placeholder — real blob stubbing is inlined in each test that uses it."""
    return None


# ── helpers ──────────────────────────────────────────────────────


def _doc(data: dict):
    """Wrap a dict as a Firestore-doc-like object (.to_dict() returns it)."""
    m = MagicMock()
    m.to_dict.return_value = data
    return m


def _ts(s: str):
    return datetime.fromisoformat(s)
