"""API tests for POST /api/search/videos — curator-free deterministic pipeline."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

MASTER = {"X-Invite-Code": "TEST-MASTER"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_master_auth():
    with patch("api.routes.auth.validate_code") as mock_validate:
        mock_validate.return_value = {"valid": True, "is_master": True}
        yield mock_validate


@pytest.fixture
def mock_search_client():
    with patch("api.routes.search._get_search_client") as mock_get:
        search_client = MagicMock()
        mock_get.return_value = search_client
        yield search_client


@pytest.fixture
def mock_interpreter():
    with patch("api.routes.search.get_search_query_interpreter") as mock_get:
        interpreter = MagicMock()
        interpreter.interpret_query.side_effect = lambda text=None, **kw: (text or "").strip()
        mock_get.return_value = interpreter
        yield interpreter


@pytest.fixture
def bq_settings():
    """Pin backend + display threshold so tests don't depend on local .env."""
    with patch("api.routes.search.get_settings") as mock_get:
        mock_get.return_value = MagicMock(search_backend="bigquery", search_display_max_distance=1.05)
        yield mock_get


def _bq_row(video_id: str, distance: float, **overrides) -> dict:
    base = {
        "result_id": f"res-{video_id}",
        "video_id": video_id,
        "video_filename": f"{video_id}.mp4",
        "text_content": "scene text",
        "chunk_index": 0,
        "timestamp_start": "00:00:05",
        "timestamp_end": "00:00:35",
        "result_data_json": '{"genre": "Drama", "chunk_summary": "a tense scene"}',
        "gcs_path": f"gs://bucket/{video_id}.mp4",
        "distance": distance,
    }
    base.update(overrides)
    return base


@pytest.mark.api
class TestSearchVideos:
    def test_deterministic_recommendations_no_llm(
        self, client, mock_master_auth, mock_search_client, mock_interpreter, bq_settings
    ):
        mock_search_client.search_videos.return_value = [
            _bq_row("v1", 0.96),
            _bq_row("v2", 0.99),
            _bq_row("v1", 1.01),  # extra chunk of v1, worse distance
        ]
        resp = client.post("/api/search/videos", json={"query": "tense drama"}, headers=MASTER)
        assert resp.status_code == 200
        body = resp.json()

        assert body["response_text"] == ""  # narration moved to the Live model
        recs = body["recommendations"]
        assert [r["video_id"] for r in recs] == ["v1", "v2"]
        assert recs[0]["video_filename"] == "v1.mp4"
        assert recs[0]["gcs_path"] == "gs://bucket/v1.mp4"
        assert recs[0]["recommendation_type"] == "clip"
        assert recs[0]["clip_start"] == "00:00:05"
        assert len(body["raw_results"]) == 2

    def test_off_topic_rows_yield_zero_recommendations(
        self, client, mock_master_auth, mock_search_client, mock_interpreter, bq_settings
    ):
        # Rows beyond the display threshold: cards are suppressed, raw results kept.
        mock_search_client.search_videos.return_value = [_bq_row("v1", 1.09), _bq_row("v2", 1.20)]
        resp = client.post("/api/search/videos", json={"query": "Hi Jay, how are you?"}, headers=MASTER)
        assert resp.status_code == 200
        body = resp.json()
        assert body["recommendations"] == []
        assert len(body["raw_results"]) == 2

    def test_empty_search_results(self, client, mock_master_auth, mock_search_client, mock_interpreter, bq_settings):
        mock_search_client.search_videos.return_value = []
        resp = client.post("/api/search/videos", json={"query": "anything"}, headers=MASTER)
        assert resp.status_code == 200
        body = resp.json()
        assert body["recommendations"] == []
        assert body["raw_results"] == []

    def test_interpreter_skipped_for_text_on_bigtable_backend(
        self, client, mock_master_auth, mock_search_client, mock_interpreter
    ):
        mock_search_client.search_videos.return_value = []
        with patch("api.routes.search.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(search_backend="bigtable", search_display_max_distance=0.6)
            resp = client.post("/api/search/videos", json={"query": "koi comedy clip"}, headers=MASTER)
        assert resp.status_code == 200
        mock_interpreter.interpret_query.assert_not_called()
        mock_search_client.search_videos.assert_called_once_with("koi comedy clip", 20, owner="")
