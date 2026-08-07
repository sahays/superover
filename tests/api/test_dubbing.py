"""API tests for the Multilingual AI Dubbing feature."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from api.main import app
from libs.db.enums import DubbingJobStatus, DubbingLanguage, DubbingMode

TEST_INVITE = {"X-Invite-Code": "TEST-CODE"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_auth():
    with patch("api.routes.auth.validate_code") as mock_validate:
        mock_validate.return_value = {"valid": True, "is_master": True}
        yield mock_validate


@pytest.fixture
def mock_db():
    with patch("api.routes.dubbing.get_db") as mock_get_db:
        db = MagicMock()
        mock_get_db.return_value = db
        yield db


@pytest.fixture
def mock_storage():
    with patch("api.routes.dubbing.get_storage") as mock_get_storage:
        storage = MagicMock()
        mock_get_storage.return_value = storage
        yield storage


def _sample_dubbing_job(**overrides):
    base = {
        "job_id": "dub-12345",
        "video_id": "vid-test-abc",
        "status": DubbingJobStatus.COMPLETED.value,
        "config": {
            "target_languages": ["hi-IN", "es-ES"],
            "voice": "Kore",
            "mode": DubbingMode.VOICEOVER.value,
            "ducking_db": -18.0,
            "source_language": "auto",
        },
        "tracks": {
            "hi-IN": {
                "language": "hi-IN",
                "language_label": "Hindi",
                "audio_gcs_path": "gs://processed/dubbing/dub-12345/dub_hi_in.wav",
                "video_gcs_path": "gs://processed/dubbing/dub-12345/video_dubbed_hi_in.mp4",
                "audio_size_bytes": 1024000,
                "video_size_bytes": 5120000,
                "segments": [
                    {
                        "speaker": "Speaker 1",
                        "start_seconds": 0.0,
                        "end_seconds": 4.5,
                        "original_text": "Hello world",
                        "translated_text": "नमस्ते दुनिया",
                        "confidence": 0.95,
                    }
                ],
                "duration_seconds": 30.0,
            }
        },
        "source_audio_path": "gs://processed/media_dialog.wav",
        "source_dialog_path": "gs://processed/media_dialog.wav",
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


class TestDubbingApi:
    """Test suite for /api/dubbing endpoints."""

    def test_create_dubbing_job_success(self, client, mock_auth, mock_db):
        mock_db.get_video.return_value = {"video_id": "vid-test-abc", "filename": "sample.mp4"}
        sample = _sample_dubbing_job(status=DubbingJobStatus.PENDING.value)
        mock_db.create_dubbing_job.return_value = sample
        mock_db.get_dubbing_job.return_value = sample

        payload = {
            "video_id": "vid-test-abc",
            "config": {
                "target_languages": ["hi-IN", "es-ES"],
                "voice": "Kore",
                "mode": "voiceover",
                "ducking_db": -18.0,
            },
        }

        resp = client.post("/api/dubbing/jobs", json=payload, headers=TEST_INVITE)
        assert resp.status_code == 201
        data = resp.json()
        assert data["job_id"] == "dub-12345"
        assert data["video_id"] == "vid-test-abc"
        assert data["status"] == "pending"

    def test_create_dubbing_job_video_not_found(self, client, mock_auth, mock_db):
        mock_db.get_video.return_value = None

        payload = {
            "video_id": "nonexistent-vid",
            "config": {"target_languages": ["hi-IN"]},
        }

        resp = client.post("/api/dubbing/jobs", json=payload, headers=TEST_INVITE)
        assert resp.status_code == 404
        assert "Video not found" in resp.json()["detail"]

    def test_create_dubbing_job_empty_languages_rejected(self, client, mock_auth, mock_db):
        mock_db.get_video.return_value = {"video_id": "vid-test-abc"}

        payload = {
            "video_id": "vid-test-abc",
            "config": {"target_languages": []},
        }

        resp = client.post("/api/dubbing/jobs", json=payload, headers=TEST_INVITE)
        assert resp.status_code == 400
        assert "target language" in resp.json()["detail"].lower()

    def test_list_dubbing_jobs(self, client, mock_auth, mock_db):
        mock_db.list_dubbing_jobs.return_value = [_sample_dubbing_job()]

        resp = client.get("/api/dubbing/jobs", headers=TEST_INVITE)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["job_id"] == "dub-12345"

    def test_get_dubbing_job_success(self, client, mock_auth, mock_db):
        mock_db.get_dubbing_job.return_value = _sample_dubbing_job()

        resp = client.get("/api/dubbing/jobs/dub-12345", headers=TEST_INVITE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "dub-12345"
        assert "hi-IN" in data["tracks"]

    def test_get_dubbing_job_not_found(self, client, mock_auth, mock_db):
        mock_db.get_dubbing_job.return_value = None

        resp = client.get("/api/dubbing/jobs/unknown-id", headers=TEST_INVITE)
        assert resp.status_code == 404

    def test_get_playback_url_success(self, client, mock_auth, mock_db, mock_storage):
        mock_db.get_dubbing_job.return_value = _sample_dubbing_job()
        mock_storage.generate_signed_download_url.return_value = "https://storage.googleapis.com/signed-test-url"

        resp = client.get("/api/dubbing/jobs/dub-12345/playback/hi-IN?media_type=video", headers=TEST_INVITE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["signed_url"] == "https://storage.googleapis.com/signed-test-url"
        assert data["language"] == "hi-IN"
        assert data["media_type"] == "video"

    def test_delete_dubbing_job_success(self, client, mock_auth, mock_db, mock_storage):
        mock_db.get_dubbing_job.return_value = _sample_dubbing_job()

        resp = client.delete("/api/dubbing/jobs/dub-12345", headers=TEST_INVITE)
        assert resp.status_code == 204
        mock_db.delete_dubbing_job.assert_called_once_with("dub-12345")
        assert mock_storage.delete_file.call_count >= 1
