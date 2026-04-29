"""Engagement analysis job operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

from .enums import EngagementJobStatus

logger = logging.getLogger(__name__)


class EngagementMixin:
    """Engagement analysis job CRUD operations."""

    def create_engagement_job(
        self,
        job_id: str,
        video_id: str,
        source_scene_job_id: str,
        barc_gcs_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create an engagement analysis job."""
        job_data = {
            "job_id": job_id,
            "video_id": video_id,
            "source_scene_job_id": source_scene_job_id,
            "barc_gcs_path": barc_gcs_path,
            "config": config or {},
            "status": EngagementJobStatus.PENDING,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        self.engagement_jobs.document(job_id).set(job_data)
        logger.info(f"Created engagement job: {job_id} for video: {video_id}")
        return self.get_engagement_job(job_id)

    def get_engagement_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get engagement job by ID."""
        doc = self.engagement_jobs.document(job_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_engagement_job_status(
        self,
        job_id: str,
        status: EngagementJobStatus,
        results: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update engagement job status and metadata."""
        update_data: Dict[str, Any] = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if results is not None:
            update_data["results"] = results
        if error_message:
            update_data["error_message"] = error_message

        self.engagement_jobs.document(job_id).update(update_data)
        logger.info(f"Updated engagement job {job_id} status to {status}")

    def list_engagement_jobs_for_video(self, video_id: str) -> List[Dict[str, Any]]:
        """List engagement jobs for a video, newest first.

        Uses a video_id-only query and sorts in Python — avoids needing a
        composite Firestore index on (video_id, created_at).
        """
        query = self.engagement_jobs.where("video_id", "==", video_id)
        jobs = [doc.to_dict() for doc in query.stream()]
        jobs.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
        return jobs

    def get_pending_engagement_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending engagement jobs for worker processing."""
        query = self.engagement_jobs.where("status", "==", EngagementJobStatus.PENDING).limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    def delete_engagement_job(self, job_id: str) -> None:
        """Delete an engagement job."""
        self.engagement_jobs.document(job_id).delete()
        logger.info(f"Deleted engagement job: {job_id}")
