"""
Critical integration tests that catch real bugs.

These tests focus on the actual bugs we encountered:
1. Route ordering (404 on /api/scenes/jobs)
2. Results filtering by job_id (multiple jobs showing same results)
3. Job-based architecture (jobs have unique URLs)
4. No legacy VideoStatus usage
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database — patch get_db in all scene sub-modules."""
    with (
        patch("api.routes.scenes.jobs.get_db") as mock_jobs,
        patch("api.routes.scenes.videos.get_db") as mock_videos,
        patch("api.routes.scenes.results.get_db") as mock_results,
    ):
        db = MagicMock()
        mock_jobs.return_value = db
        mock_videos.return_value = db
        mock_results.return_value = db
        yield db


class TestCriticalRouting:
    """Test route ordering bugs that caused 404 errors."""

    def test_jobs_route_not_caught_by_video_id_route(self, client, mock_db):
        """
        CRITICAL: /api/scenes/jobs must not be caught by /{video_id} route.
        This was a real bug - "jobs" was being treated as a video_id.
        """
        mock_db.scene_jobs = MagicMock()
        mock_db.scene_jobs.where.return_value.order_by.return_value.limit.return_value.stream.return_value = []

        response = client.get("/api/scenes/jobs")

        # Should NOT be 404 (which would mean /{video_id} caught it)
        assert response.status_code == 200, "Route /api/scenes/jobs returned 404 - route ordering bug!"
        assert isinstance(response.json(), list)

    def test_job_results_route_exists(self, client, mock_db):
        """
        CRITICAL: /api/scenes/jobs/{job_id}/results must exist for job-specific results.
        This was added to fix multiple jobs showing same results.
        """
        mock_db.get_scene_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
        }
        mock_db.get_results_for_job.return_value = []

        response = client.get("/api/scenes/jobs/job-123/results")

        assert response.status_code == 200, "Job-specific results endpoint missing!"
        assert isinstance(response.json(), list)


class TestJobBasedArchitecture:
    """Test that job-based architecture works correctly."""

    def test_scene_jobs_have_unique_ids(self, client, mock_db):
        """
        CRITICAL: Each scene job must have unique job_id, not video_id.
        Multiple jobs for same video must be distinguishable.
        """
        jobs = [
            {
                "job_id": "job-1",
                "video_id": "video-123",
                "status": "completed",
                "config": {"chunk_duration": 0},
                "prompt_text": "Analyze...",
            },
            {
                "job_id": "job-2",
                "video_id": "video-123",
                "status": "completed",
                "config": {"chunk_duration": 30},
                "prompt_text": "Analyze...",
            },
        ]

        # Mock the query chain
        mock_query = MagicMock()
        mock_db.scene_jobs = mock_query
        mock_query.order_by.return_value.limit.return_value.stream.return_value = [
            MagicMock(to_dict=lambda j=jobs[0]: j),
            MagicMock(to_dict=lambda j=jobs[1]: j),
        ]

        response = client.get("/api/scenes/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["job_id"] == "job-1"
        assert data[1]["job_id"] == "job-2"
        # Same video, different jobs!
        assert data[0]["video_id"] == data[1]["video_id"]

    def test_results_filtered_by_job_id(self, client, mock_db):
        """
        CRITICAL: Results must be filtered by scene_job_id, not just video_id.
        This was a real bug - all jobs for same video showed same results.
        """
        mock_db.get_scene_job.return_value = {
            "job_id": "job-1",
            "video_id": "video-123",
        }
        job1_results = [
            {
                "video_id": "video-123",
                "scene_job_id": "job-1",
                "result_type": "scene_analysis",
                "result_data": {"chunk": 0},
            }
        ]
        mock_db.get_results_for_job.return_value = job1_results

        response = client.get("/api/scenes/jobs/job-1/results")

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1, "Should only return results for this specific job!"


class TestNoLegacyCode:
    """Ensure legacy VideoStatus code is removed."""

    def test_video_creation_no_status_field(self, client, mock_db):
        """
        CRITICAL: Videos should not have status field (legacy).
        Status lives in jobs now (media_jobs, scene_jobs).
        """
        mock_db.create_video.return_value = {
            "video_id": "new-video",
            "filename": "test.mp4",
            "gcs_path": "gs://bucket/test.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1000000,
            # Note: no "status" field!
        }

        response = client.post(
            "/api/scenes",
            json={
                "filename": "test.mp4",
                "gcs_path": "gs://bucket/test.mp4",
                "content_type": "video/mp4",
                "size_bytes": 1000000,
            },
        )

        assert response.status_code == 201
        # Video should not have status - that's in jobs
        created_video = mock_db.create_video.call_args[1]
        assert "status" not in str(created_video), "Video creation should not set status!"

    def test_scene_job_processing_does_not_update_video_status(self, client, mock_db):
        """
        CRITICAL: Creating a scene job should NOT update video.status.
        Video status is legacy - only jobs have status.
        """
        mock_db.get_video.return_value = {
            "video_id": "video-123",
            "filename": "test.mp4",
        }
        mock_db.get_prompt.return_value = {"prompt_text": "Analyze..."}
        mock_db.create_scene_job.return_value = {
            "job_id": "job-123",
            "video_id": "video-123",
            "status": "pending",
            "config": {},
        }

        response = client.post("/api/scenes/video-123/process", json={"chunk_duration": 30})

        assert response.status_code == 200
        # Should NOT have called update_video_status (method removed)
        assert not hasattr(mock_db, "update_video_status") or not mock_db.update_video_status.called


class TestWorkflowSeparation:
    """Test that media and scene workflows are properly separated."""

    def test_scene_workflow_requires_compressed_video_path(self, client, mock_db):
        """
        CRITICAL: Scene workflow should receive compressed video from media workflow.
        Scene worker should NOT compress - that's done in media workflow.
        """
        mock_db.get_video.return_value = {"video_id": "video-123"}
        mock_db.get_prompt.return_value = {"prompt_text": "Analyze..."}
        mock_db.create_scene_job.return_value = {
            "job_id": "job-123",
            "status": "pending",
            "config": {"compressed_video_path": "gs://bucket/compressed.mp4"},
        }

        response = client.post(
            "/api/scenes/video-123/process",
            json={
                "compressed_video_path": "gs://bucket/compressed.mp4",
                "chunk_duration": 30,
            },
        )

        assert response.status_code == 200
        # Verify compressed_video_path was passed to job config
        job_config = mock_db.create_scene_job.call_args[1]["config"]
        assert job_config["compressed_video_path"] == "gs://bucket/compressed.mp4"
