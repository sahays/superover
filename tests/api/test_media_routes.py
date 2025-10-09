"""Tests for media processing API routes."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app
from libs.database import MediaJobStatus


client = TestClient(app)


class TestMediaRoutes:
    """Test media processing API endpoints."""

    @patch('api.routes.media.get_db')
    def test_create_media_job_success(self, mock_get_db):
        """Test creating a media processing job."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_video.return_value = {
            "video_id": "video-123",
            "filename": "test.mp4",
            "status": "completed"
        }

        mock_db.create_media_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": "pending",
            "config": {
                "compress": True,
                "compress_resolution": "480p",
                "extract_audio": True,
                "audio_format": "mp3",
                "audio_bitrate": "128k",
                "crf": 23,
                "preset": "medium"
            },
            "created_at": "2025-01-01T00:00:00Z"
        }

        # Execute
        response = client.post(
            "/api/media/jobs",
            json={
                "video_id": "video-123",
                "config": {
                    "compress": True,
                    "compress_resolution": "480p"
                }
            }
        )

        # Verify
        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["video_id"] == "video-123"
        assert data["status"] == "pending"

    @patch('api.routes.media.get_db')
    def test_create_media_job_video_not_found(self, mock_get_db):
        """Test creating job for non-existent video."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.get_video.return_value = None

        response = client.post(
            "/api/media/jobs",
            json={"video_id": "nonexistent"}
        )

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

    @patch('api.routes.media.get_db')
    def test_get_media_job(self, mock_get_db):
        """Test getting a media job by ID."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_media_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": "completed",
            "config": {},
            "results": {
                "metadata": {"duration": 60.0},
                "compressed_video_path": "gs://bucket/compressed.mp4",
                "compression_ratio": 45.5
            }
        }

        response = client.get("/api/media/jobs/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "completed"
        assert "results" in data

    @patch('api.routes.media.get_db')
    def test_get_media_job_not_found(self, mock_get_db):
        """Test getting non-existent media job."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.get_media_job.return_value = None

        response = client.get("/api/media/jobs/nonexistent")

        assert response.status_code == 404
        assert "Media job not found" in response.json()["detail"]

    @patch('api.routes.media.get_db')
    def test_list_media_jobs_for_video(self, mock_get_db):
        """Test listing all media jobs for a video."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_video.return_value = {"video_id": "video-123"}
        mock_db.list_media_jobs_for_video.return_value = [
            {
                "job_id": "job-1",
                "video_id": "video-123",
                "status": "completed",
                "config": {
                    "compress": True,
                    "compress_resolution": "480p",
                    "extract_audio": True,
                    "audio_format": "mp3",
                    "audio_bitrate": "128k",
                    "crf": 23,
                    "preset": "medium"
                }
            },
            {
                "job_id": "job-2",
                "video_id": "video-123",
                "status": "processing",
                "config": {
                    "compress": True,
                    "compress_resolution": "720p",
                    "extract_audio": True,
                    "audio_format": "mp3",
                    "audio_bitrate": "128k",
                    "crf": 23,
                    "preset": "medium"
                }
            }
        ]

        response = client.get("/api/media/jobs/video/video-123")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["job_id"] == "job-1"
        assert data[1]["job_id"] == "job-2"

    @patch('api.routes.media.get_db')
    def test_list_media_jobs_with_status_filter(self, mock_get_db):
        """Test listing media jobs filtered by status."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_video.return_value = {"video_id": "video-123"}
        mock_db.list_media_jobs_for_video.return_value = [
            {
                "job_id": "job-1",
                "video_id": "video-123",
                "status": "completed",
                "config": {
                    "compress": True,
                    "compress_resolution": "480p",
                    "extract_audio": True,
                    "audio_format": "mp3",
                    "audio_bitrate": "128k",
                    "crf": 23,
                    "preset": "medium"
                }
            }
        ]

        response = client.get("/api/media/jobs/video/video-123?status_filter=completed")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"

    @patch('api.routes.media.get_db')
    def test_delete_media_job_success(self, mock_get_db):
        """Test deleting a media job."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_media_job.return_value = {
            "job_id": "job-123",
            "status": "completed"
        }

        response = client.delete("/api/media/jobs/job-123")

        assert response.status_code == 204
        mock_db.delete_media_job.assert_called_once_with("job-123")

    @patch('api.routes.media.get_db')
    def test_delete_media_job_not_found(self, mock_get_db):
        """Test deleting non-existent media job."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.get_media_job.return_value = None

        response = client.delete("/api/media/jobs/nonexistent")

        assert response.status_code == 404

    @patch('api.routes.media.get_db')
    def test_delete_processing_job_fails(self, mock_get_db):
        """Test cannot delete job that is currently processing."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_media_job.return_value = {
            "job_id": "job-123",
            "status": MediaJobStatus.PROCESSING
        }

        response = client.delete("/api/media/jobs/job-123")

        assert response.status_code == 400
        assert "currently processing" in response.json()["detail"]
        mock_db.delete_media_job.assert_not_called()

    def test_get_media_presets(self):
        """Test getting available media processing presets."""
        response = client.get("/api/media/presets")

        assert response.status_code == 200
        data = response.json()
        assert "resolutions" in data
        assert "audio_formats" in data
        assert "audio_bitrates" in data
        assert "presets" in data
        assert "crf_range" in data

        assert "480p" in data["resolutions"]
        assert "mp3" in data["audio_formats"]
        assert "128k" in data["audio_bitrates"]
        assert "medium" in data["presets"]
        assert data["crf_range"]["default"] == 23


class TestMediaJobValidation:
    """Test request validation for media endpoints."""

    def test_create_job_missing_video_id(self):
        """Test creating job without video_id fails."""
        response = client.post(
            "/api/media/jobs",
            json={"config": {}}
        )

        assert response.status_code == 422

    def test_create_job_with_default_config(self):
        """Test creating job uses default config when not provided."""
        with patch('api.routes.media.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.get_video.return_value = {"video_id": "video-123"}
            mock_db.create_media_job.return_value = {
                "job_id": "job-123",
                "video_id": "video-123",
                "status": "pending",
                "config": {
                    "compress": True,
                    "compress_resolution": "480p",
                    "extract_audio": True,
                    "audio_format": "mp3",
                    "audio_bitrate": "128k",
                    "crf": 23,
                    "preset": "medium"
                }
            }

            response = client.post(
                "/api/media/jobs",
                json={"video_id": "video-123"}
            )

            assert response.status_code == 201
            # Verify default config was used
            call_args = mock_db.create_media_job.call_args
            config = call_args[1]["config"]
            assert config["compress_resolution"] == "480p"
            assert config["audio_format"] == "mp3"
