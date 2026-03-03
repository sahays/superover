"""Media job operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

from .enums import MediaJobStatus

logger = logging.getLogger(__name__)


class MediaMixin:
    """Media job CRUD and transcoder tracking operations."""

    def create_media_job(self, job_id: str, video_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a media processing job."""
        job_data = {
            "job_id": job_id,
            "video_id": video_id,
            "status": MediaJobStatus.PENDING,
            "config": config,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        self.media_jobs.document(job_id).set(job_data)
        logger.info(f"Created media job: {job_id} for video: {video_id}")
        return self.get_media_job(job_id)

    def get_media_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get media job by ID."""
        doc = self.media_jobs.document(job_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_media_job_status(
        self,
        job_id: str,
        status: MediaJobStatus,
        results: Optional[Dict[str, Any]] = None,
        progress: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update media job status and optionally store results."""
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if results:
            update_data["results"] = results

        if progress:
            update_data["progress"] = progress

        if error_message:
            update_data["error_message"] = error_message

        self.media_jobs.document(job_id).update(update_data)
        logger.info(f"Updated media job {job_id} status to {status}")

    def list_media_jobs_for_video(self, video_id: str, status: Optional[MediaJobStatus] = None) -> List[Dict[str, Any]]:
        """List all media jobs for a video."""
        query = self.media_jobs.where("video_id", "==", video_id)

        if status:
            query = query.where("status", "==", status)

        return [doc.to_dict() for doc in query.stream()]

    def get_pending_media_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending media jobs for worker processing."""
        query = self.media_jobs.where("status", "==", MediaJobStatus.PENDING).limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    def update_media_job_transcoder(
        self,
        job_id: str,
        transcoder_job_name: str,
        phase: str = "media",
    ) -> None:
        """Store Transcoder API job reference for polling."""
        update_data = {
            "status": MediaJobStatus.TRANSCODING,
            "transcoder_job_name": transcoder_job_name,
            "transcoder_phase": phase,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.media_jobs.document(job_id).update(update_data)
        logger.info(f"Updated media job {job_id} with transcoder job: {transcoder_job_name} (phase={phase})")

    def get_transcoding_media_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get media jobs currently in TRANSCODING state."""
        query = self.media_jobs.where("status", "==", MediaJobStatus.TRANSCODING).limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    def delete_media_job(self, job_id: str) -> None:
        """Delete a media job."""
        self.media_jobs.document(job_id).delete()
        logger.info(f"Deleted media job: {job_id}")
