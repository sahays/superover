"""Tests for scene API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, Mock
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.main import app
from libs.database import VideoStatus


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database."""
    with patch('api.routes.scenes.get_db') as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


@pytest.fixture
def mock_storage():
    """Mock storage."""
    with patch('api.routes.scenes.get_storage') as mock:
        storage = MagicMock()
        mock.return_value = storage
        yield storage


class TestListScenes:
    """Tests for GET /api/scenes endpoint."""

    def test_list_scenes_success(self, client, mock_db, sample_video_metadata):
        """Test successful scene listing."""
        mock_db.list_videos.return_value = [sample_video_metadata]

        response = client.get("/api/scenes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["video_id"] == "test-video-123"
        assert data[0]["filename"] == "test_video.mp4"
        mock_db.list_videos.assert_called_once()

    def test_list_scenes_empty(self, client, mock_db):
        """Test listing when no scenes exist."""
        mock_db.list_videos.return_value = []

        response = client.get("/api/scenes")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_scenes_with_status_filter(self, client, mock_db, sample_video_metadata):
        """Test filtering scenes by status."""
        mock_db.list_videos.return_value = [sample_video_metadata]

        response = client.get("/api/scenes?status=completed")

        assert response.status_code == 200
        mock_db.list_videos.assert_called_once()


class TestGetScene:
    """Tests for GET /api/scenes/{video_id} endpoint."""

    def test_get_scene_success(self, client, mock_db, sample_video_metadata):
        """Test successful scene retrieval."""
        mock_db.get_video.return_value = sample_video_metadata

        response = client.get("/api/scenes/test-video-123")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "test-video-123"
        assert data["filename"] == "test_video.mp4"

    def test_get_scene_not_found(self, client, mock_db):
        """Test getting non-existent scene."""
        mock_db.get_video.return_value = None

        response = client.get("/api/scenes/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSignedUrl:
    """Tests for POST /api/scenes/signed-url endpoint."""

    def test_get_signed_url_success(self, client, mock_storage):
        """Test successful signed URL generation."""
        mock_storage.generate_signed_upload_url.return_value = (
            "https://signed-url.com",
            "gs://bucket/video.mp4"
        )

        response = client.post(
            "/api/scenes/signed-url",
            json={
                "filename": "upload.mp4",
                "content_type": "video/mp4"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["signed_url"] == "https://signed-url.com"
        assert data["gcs_path"] == "gs://bucket/video.mp4"
        assert "expires_in_minutes" in data

    def test_get_signed_url_error(self, client, mock_storage):
        """Test signed URL generation error."""
        mock_storage.generate_signed_upload_url.side_effect = Exception("Storage error")

        response = client.post(
            "/api/scenes/signed-url",
            json={
                "filename": "upload.mp4",
                "content_type": "video/mp4"
            }
        )

        assert response.status_code == 500


class TestCreateScene:
    """Tests for POST /api/scenes endpoint."""

    def test_create_scene_success(self, client, mock_db):
        """Test successful scene creation."""
        mock_db.create_video.return_value = {
            "video_id": "new-video-123",
            "filename": "upload.mp4",
            "status": "uploaded",
            "gcs_path": "gs://bucket/new-video-123.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1024000
        }

        response = client.post(
            "/api/scenes",
            json={
                "filename": "upload.mp4",
                "gcs_path": "gs://bucket/new-video-123.mp4",
                "content_type": "video/mp4",
                "size_bytes": 1024000
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["video_id"] == "new-video-123"
        assert data["filename"] == "upload.mp4"


class TestProcessScene:
    """Tests for POST /api/scenes/{video_id}/process endpoint."""

    def test_process_scene_success(self, client, mock_db, sample_video_metadata):
        """Test successful scene processing initiation."""
        mock_db.get_video.return_value = sample_video_metadata
        mock_db.create_task.return_value = {
            "task_id": "task-123",
            "video_id": "test-video-123",
            "task_type": "video_processing",
            "status": "pending"
        }

        response = client.post(
            "/api/scenes/test-video-123/process",
            json={
                "compress": True,
                "chunk": True,
                "extract_audio": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "test-video-123"
        assert data["status"] == "processing"

    def test_process_scene_not_found(self, client, mock_db):
        """Test processing for non-existent scene."""
        mock_db.get_video.return_value = None

        response = client.post(
            "/api/scenes/nonexistent/process",
            json={
                "compress": True,
                "chunk": True,
                "extract_audio": True
            }
        )

        assert response.status_code == 404


class TestDeleteScene:
    """Tests for DELETE /api/scenes/{video_id} endpoint."""

    def test_delete_scene_success(self, client, mock_db, mock_storage, sample_video_metadata):
        """Test successful scene deletion."""
        mock_db.get_video.return_value = sample_video_metadata
        mock_db.get_manifest.return_value = {
            "video_id": "test-video-123",
            "compressed": {"gcs_path": "gs://bucket/compressed.mp4"},
            "chunks": {
                "items": [
                    {"gcs_path": "gs://bucket/chunk1.mp4"},
                    {"gcs_path": "gs://bucket/chunk2.mp4"}
                ]
            },
            "audio": {"gcs_path": "gs://bucket/audio.mp3"}
        }
        mock_db.list_tasks_for_video.return_value = []
        mock_db.get_results_for_video.return_value = []

        response = client.delete("/api/scenes/test-video-123")

        assert response.status_code == 204
        mock_storage.delete_file.assert_called()

    def test_delete_scene_not_found(self, client, mock_db):
        """Test deleting non-existent scene."""
        mock_db.get_video.return_value = None

        response = client.delete("/api/scenes/nonexistent")

        assert response.status_code == 404


class TestGetResults:
    """Tests for GET /api/scenes/{video_id}/results endpoint."""

    def test_get_results_success(self, client, mock_db):
        """Test successful results retrieval."""
        mock_results = [
            {
                "video_id": "test-video-123",
                "result_type": "scene_analysis",
                "result_data": {"summary": "Test scene"}
            }
        ]
        mock_db.get_results_for_video.return_value = mock_results

        response = client.get("/api/scenes/test-video-123/results")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["result_type"] == "scene_analysis"

    def test_get_results_with_type_filter(self, client, mock_db):
        """Test filtering results by type."""
        mock_db.get_results_for_video.return_value = []

        response = client.get("/api/scenes/test-video-123/results?result_type=scene_analysis")

        assert response.status_code == 200
        mock_db.get_results_for_video.assert_called_once_with(
            "test-video-123",
            result_type="scene_analysis"
        )
