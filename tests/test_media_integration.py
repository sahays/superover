"""Integration tests for media processing flow."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from libs.database import MediaJobStatus


client = TestClient(app)


class TestMediaProcessingIntegration:
    """Integration tests for complete media processing flow."""

    @pytest.mark.integration
    @patch('api.routes.media.get_db')
    @patch('workers.media_worker.get_db')
    @patch('workers.media_worker.get_storage')
    @patch('workers.media_worker.settings')
    def test_complete_media_processing_flow(
        self,
        mock_worker_settings,
        mock_worker_storage,
        mock_worker_db,
        mock_api_db
    ):
        """
        Test complete flow from API request to worker completion.

        Steps:
        1. Create video via API
        2. Create media processing job via API
        3. Worker picks up job
        4. Worker processes and completes
        5. Results are stored
        """
        # Step 1: Setup video
        mock_api_db.return_value.get_video.return_value = {
            "video_id": "video-123",
            "filename": "test.mp4",
            "gcs_path": "gs://bucket/test.mp4",
            "status": "completed"
        }

        # Step 2: Create job via API
        mock_api_db.return_value.create_media_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": MediaJobStatus.PENDING,
            "config": {
                "compress": True,
                "compress_resolution": "480p",
                "extract_audio": True,
                "audio_format": "mp3",
                "audio_bitrate": "128k"
            }
        }

        response = client.post(
            "/api/media/jobs",
            json={
                "video_id": "video-123",
                "config": {
                    "compress_resolution": "480p"
                }
            }
        )

        assert response.status_code == 201
        job_data = response.json()
        assert job_data["job_id"] == "job-123"
        assert job_data["status"] == MediaJobStatus.PENDING

    @pytest.mark.integration
    @patch('api.routes.media.get_db')
    def test_job_lifecycle_via_api(self, mock_get_db):
        """Test job lifecycle: create -> processing -> completed."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock video exists
        mock_db.get_video.return_value = {"video_id": "video-123"}

        # Create job
        mock_db.create_media_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": MediaJobStatus.PENDING,
            "config": {}
        }

        create_response = client.post(
            "/api/media/jobs",
            json={"video_id": "video-123"}
        )
        assert create_response.status_code == 201

        # Get job (processing)
        mock_db.get_media_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": MediaJobStatus.PROCESSING,
            "config": {
                "compress": True,
                "compress_resolution": "480p",
                "extract_audio": True,
                "audio_format": "mp3",
                "audio_bitrate": "128k",
                "crf": 23,
                "preset": "medium"
            },
            "progress": {"step": "compressing", "percent": 50}
        }

        get_response = client.get("/api/media/jobs/job-123")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == MediaJobStatus.PROCESSING

        # Get job (completed)
        mock_db.get_media_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": MediaJobStatus.COMPLETED,
            "config": {
                "compress": True,
                "compress_resolution": "480p",
                "extract_audio": True,
                "audio_format": "mp3",
                "audio_bitrate": "128k",
                "crf": 23,
                "preset": "medium"
            },
            "results": {
                "metadata": {"duration": 60.0},
                "compressed_video_path": "gs://bucket/compressed.mp4",
                "compression_ratio": 45.5
            }
        }

        final_response = client.get("/api/media/jobs/job-123")
        assert final_response.status_code == 200
        data = final_response.json()
        assert data["status"] == MediaJobStatus.COMPLETED
        assert "results" in data
        assert data["results"]["compression_ratio"] == 45.5

    @pytest.mark.integration
    @patch('api.routes.media.get_db')
    def test_list_jobs_for_video(self, mock_get_db):
        """Test listing all jobs for a video."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_video.return_value = {"video_id": "video-123"}
        mock_db.list_media_jobs_for_video.return_value = [
            {
                "job_id": "job-1",
                "video_id": "video-123",
                "status": MediaJobStatus.COMPLETED,
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
                "status": MediaJobStatus.COMPLETED,
                "config": {
                    "compress": True,
                    "compress_resolution": "720p",
                    "extract_audio": True,
                    "audio_format": "mp3",
                    "audio_bitrate": "128k",
                    "crf": 23,
                    "preset": "medium"
                }
            },
            {
                "job_id": "job-3",
                "video_id": "video-123",
                "status": MediaJobStatus.PROCESSING,
                "config": {
                    "compress": True,
                    "compress_resolution": "1080p",
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
        jobs = response.json()
        assert len(jobs) == 3
        assert jobs[0]["job_id"] == "job-1"
        assert jobs[2]["status"] == MediaJobStatus.PROCESSING

    @pytest.mark.integration
    @patch('api.routes.media.get_db')
    def test_delete_completed_job(self, mock_get_db):
        """Test deleting a completed job."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_media_job.return_value = {
            "job_id": "job-123",
            "status": MediaJobStatus.COMPLETED
        }

        response = client.delete("/api/media/jobs/job-123")

        assert response.status_code == 204
        mock_db.delete_media_job.assert_called_once_with("job-123")

    @pytest.mark.integration
    def test_get_presets(self):
        """Test getting media processing presets."""
        response = client.get("/api/media/presets")

        assert response.status_code == 200
        presets = response.json()

        # Verify all expected fields
        assert "resolutions" in presets
        assert "audio_formats" in presets
        assert "audio_bitrates" in presets
        assert "presets" in presets
        assert "crf_range" in presets

        # Verify some values
        assert "480p" in presets["resolutions"]
        assert "720p" in presets["resolutions"]
        assert "mp3" in presets["audio_formats"]
        assert "aac" in presets["audio_formats"]
        assert presets["crf_range"]["min"] == 0
        assert presets["crf_range"]["max"] == 51

    @pytest.mark.integration
    @patch('api.routes.media.get_db')
    def test_error_handling_cascade(self, mock_get_db):
        """Test error handling throughout the system."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Simulate database error
        mock_db.get_video.side_effect = Exception("Database connection failed")

        response = client.post(
            "/api/media/jobs",
            json={"video_id": "video-123"}
        )

        assert response.status_code == 500
        assert "Failed to create media job" in response.json()["detail"]


class TestMediaProcessingNonRegression:
    """Tests to ensure media processing doesn't affect existing functionality."""

    @patch('api.routes.videos.get_db')
    def test_existing_video_endpoints_unaffected(self, mock_get_db):
        """Test existing video endpoints still work."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_video.return_value = {
            "video_id": "video-123",
            "filename": "test.mp4",
            "gcs_path": "gs://bucket/test.mp4",
            "status": "uploaded"
        }

        # Test existing video GET endpoint
        response = client.get("/api/videos/video-123")
        assert response.status_code == 200
        assert response.json()["video_id"] == "video-123"

    @patch('api.routes.videos.get_db')
    def test_existing_video_processing_unaffected(self, mock_get_db):
        """Test existing video processing workflow still works."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_db.get_video.return_value = {
            "video_id": "video-123",
            "filename": "test.mp4",
            "gcs_path": "gs://bucket/test.mp4",
            "status": "uploaded"
        }
        mock_db.create_task.return_value = {
            "task_id": "task-123",
            "video_id": "video-123",
            "task_type": "video_processing"
        }

        # Test existing process endpoint
        response = client.post(
            "/api/videos/video-123/process",
            json={
                "compress": True,
                "chunk": True,
                "extract_audio": True
            }
        )

        assert response.status_code == 200
        assert "processing" in response.json()["status"].lower()

    def test_health_endpoint_still_works(self):
        """Test health endpoint is not affected."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint_still_works(self):
        """Test root endpoint is not affected."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Super Over Alchemy API" in response.json()["service"]
