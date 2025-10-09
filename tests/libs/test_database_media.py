"""Tests for media jobs database operations."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from libs.database import FirestoreDB, MediaJobStatus


class TestMediaJobOperations:
    """Test media job database operations."""

    @pytest.fixture
    def db(self, mock_firestore_client):
        """Create a FirestoreDB instance with mocked client."""
        with patch('libs.database.firestore.Client', return_value=mock_firestore_client):
            db = FirestoreDB()
            db.media_jobs = MagicMock()
            return db

    @pytest.fixture
    def sample_media_job(self):
        """Sample media job data."""
        return {
            "job_id": "job-123",
            "video_id": "video-456",
            "status": MediaJobStatus.PENDING,
            "config": {
                "compress": True,
                "compress_resolution": "480p",
                "extract_audio": True,
                "audio_format": "mp3",
                "audio_bitrate": "128k",
                "crf": 23,
                "preset": "medium"
            },
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

    def test_create_media_job(self, db, sample_media_job):
        """Test creating a media job."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.get.return_value.exists = True
        mock_doc.get.return_value.to_dict.return_value = sample_media_job
        db.media_jobs.document.return_value = mock_doc

        # Execute
        result = db.create_media_job(
            job_id=sample_media_job["job_id"],
            video_id=sample_media_job["video_id"],
            config=sample_media_job["config"]
        )

        # Verify
        db.media_jobs.document.assert_called_with(sample_media_job["job_id"])
        mock_doc.set.assert_called_once()
        assert result["job_id"] == sample_media_job["job_id"]
        assert result["video_id"] == sample_media_job["video_id"]
        assert result["status"] == MediaJobStatus.PENDING

    def test_get_media_job(self, db, sample_media_job):
        """Test getting a media job by ID."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.get.return_value.exists = True
        mock_doc.get.return_value.to_dict.return_value = sample_media_job
        db.media_jobs.document.return_value = mock_doc

        # Execute
        result = db.get_media_job(sample_media_job["job_id"])

        # Verify
        db.media_jobs.document.assert_called_with(sample_media_job["job_id"])
        assert result == sample_media_job

    def test_get_media_job_not_found(self, db):
        """Test getting a non-existent media job."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.get.return_value.exists = False
        db.media_jobs.document.return_value = mock_doc

        # Execute
        result = db.get_media_job("nonexistent")

        # Verify
        assert result is None

    def test_update_media_job_status(self, db):
        """Test updating media job status."""
        # Setup mock
        mock_doc = MagicMock()
        db.media_jobs.document.return_value = mock_doc

        results = {
            "metadata": {"duration": 60.0},
            "compressed_video_path": "gs://bucket/compressed.mp4",
            "audio_path": "gs://bucket/audio.mp3"
        }

        progress = {"step": "compressing", "percent": 50}

        # Execute
        db.update_media_job_status(
            job_id="job-123",
            status=MediaJobStatus.PROCESSING,
            results=results,
            progress=progress
        )

        # Verify
        db.media_jobs.document.assert_called_with("job-123")
        mock_doc.update.assert_called_once()

        call_args = mock_doc.update.call_args[0][0]
        assert call_args["status"] == MediaJobStatus.PROCESSING
        assert call_args["results"] == results
        assert call_args["progress"] == progress

    def test_update_media_job_with_error(self, db):
        """Test updating media job with error message."""
        mock_doc = MagicMock()
        db.media_jobs.document.return_value = mock_doc

        db.update_media_job_status(
            job_id="job-123",
            status=MediaJobStatus.FAILED,
            error_message="Processing failed"
        )

        call_args = mock_doc.update.call_args[0][0]
        assert call_args["status"] == MediaJobStatus.FAILED
        assert call_args["error_message"] == "Processing failed"

    def test_list_media_jobs_for_video(self, db, sample_media_job):
        """Test listing all media jobs for a video."""
        # Setup mock
        mock_query = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = sample_media_job
        mock_query.stream.return_value = [mock_doc]
        db.media_jobs.where.return_value = mock_query

        # Execute
        results = db.list_media_jobs_for_video("video-456")

        # Verify
        db.media_jobs.where.assert_called_with("video_id", "==", "video-456")
        assert len(results) == 1
        assert results[0] == sample_media_job

    def test_list_media_jobs_with_status_filter(self, db, sample_media_job):
        """Test listing media jobs filtered by status."""
        # Setup mock
        mock_query = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = sample_media_job
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]
        db.media_jobs.where.return_value = mock_query

        # Execute
        results = db.list_media_jobs_for_video(
            "video-456",
            status=MediaJobStatus.COMPLETED
        )

        # Verify
        assert len(results) == 1

    def test_get_pending_media_jobs(self, db, sample_media_job):
        """Test getting pending media jobs for worker."""
        # Setup mocks
        mock_query = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = sample_media_job
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]
        db.media_jobs.where.return_value = mock_query

        # Execute
        results = db.get_pending_media_jobs(limit=10)

        # Verify
        db.media_jobs.where.assert_called_with("status", "==", MediaJobStatus.PENDING)
        mock_query.limit.assert_called_with(10)
        assert len(results) == 1
        assert results[0] == sample_media_job

    def test_get_pending_media_jobs_sorted(self, db):
        """Test pending jobs are sorted by created_at."""
        job1 = {"job_id": "1", "created_at": datetime(2025, 1, 1, 10, 0)}
        job2 = {"job_id": "2", "created_at": datetime(2025, 1, 1, 9, 0)}
        job3 = {"job_id": "3", "created_at": datetime(2025, 1, 1, 11, 0)}

        mock_query = MagicMock()
        mock_docs = [
            MagicMock(to_dict=MagicMock(return_value=job1)),
            MagicMock(to_dict=MagicMock(return_value=job2)),
            MagicMock(to_dict=MagicMock(return_value=job3))
        ]
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = mock_docs
        db.media_jobs.where.return_value = mock_query

        results = db.get_pending_media_jobs(limit=10)

        # Should be sorted oldest first
        assert results[0]["job_id"] == "2"  # 9:00
        assert results[1]["job_id"] == "1"  # 10:00
        assert results[2]["job_id"] == "3"  # 11:00

    def test_delete_media_job(self, db):
        """Test deleting a media job."""
        mock_doc = MagicMock()
        db.media_jobs.document.return_value = mock_doc

        db.delete_media_job("job-123")

        db.media_jobs.document.assert_called_with("job-123")
        mock_doc.delete.assert_called_once()


class TestMediaJobStatus:
    """Test MediaJobStatus enum."""

    def test_all_statuses(self):
        """Test all status values."""
        assert MediaJobStatus.PENDING == "pending"
        assert MediaJobStatus.PROCESSING == "processing"
        assert MediaJobStatus.COMPLETED == "completed"
        assert MediaJobStatus.FAILED == "failed"

    def test_status_comparison(self):
        """Test status enum comparison."""
        assert MediaJobStatus.PENDING == MediaJobStatus.PENDING
        assert MediaJobStatus.PENDING != MediaJobStatus.COMPLETED
