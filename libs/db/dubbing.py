"""Dubbing job operations mixin for FirestoreDB."""

import logging
from typing import Any, Dict, List, Optional
from google.cloud import firestore
from .enums import DubbingJobStatus

logger = logging.getLogger(__name__)


class DubbingMixin:
    """Dubbing job CRUD operations for Firestore."""

    def create_dubbing_job(
        self,
        job_id: str,
        video_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new multilingual dubbing job record.

        Args:
            job_id: Unique job UUID.
            video_id: Source video identifier.
            config: Dubbing configuration dictionary.
        """
        logger.info(
            f"[DubbingMixin] Creating dubbing job: job_id={job_id}, video_id={video_id}, "
            f"targets={config.get('target_languages')}, voice={config.get('voice')}, mode={config.get('mode')}"
        )
        job_data = {
            "job_id": job_id,
            "video_id": video_id,
            "status": DubbingJobStatus.PENDING.value,
            "config": config,
            "tracks": {},
            "source_audio_path": None,
            "source_dialog_path": None,
            "error_message": None,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        self.dubbing_jobs.document(job_id).set(job_data)
        logger.info(f"[DubbingMixin] Dubbing job {job_id} successfully stored in Firestore")
        return self.get_dubbing_job(job_id) or job_data

    def get_dubbing_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a dubbing job by ID."""
        doc = self.dubbing_jobs.document(job_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_dubbing_job_status(
        self,
        job_id: str,
        status: DubbingJobStatus,
        source_audio_path: Optional[str] = None,
        source_dialog_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the processing status of a dubbing job."""
        update_data: Dict[str, Any] = {
            "status": status.value if hasattr(status, "value") else str(status),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if source_audio_path is not None:
            update_data["source_audio_path"] = source_audio_path
        if source_dialog_path is not None:
            update_data["source_dialog_path"] = source_dialog_path
        if error_message is not None:
            update_data["error_message"] = error_message

        self.dubbing_jobs.document(job_id).update(update_data)
        logger.info(f"[DubbingMixin] Updated dubbing job {job_id} status to {status}")

    def update_dubbing_track_result(
        self,
        job_id: str,
        language: str,
        track_info: Dict[str, Any],
    ) -> None:
        """Add or update a completed language track within a dubbing job."""
        logger.info(f"[DubbingMixin] Updating dubbing track {language} for job {job_id}")
        self.dubbing_jobs.document(job_id).update({
            f"tracks.{language}": track_info,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

    def list_dubbing_jobs(
        self,
        limit: int = 50,
        status: Optional[DubbingJobStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List dubbing jobs ordered by creation timestamp descending."""
        query = self.dubbing_jobs.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        if status is not None:
            query = query.where("status", "==", status.value if hasattr(status, "value") else str(status))

        return [doc.to_dict() for doc in query.stream()]

    def list_dubbing_jobs_for_video(self, video_id: str) -> List[Dict[str, Any]]:
        """List all dubbing jobs for a specific video."""
        query = self.dubbing_jobs.where("video_id", "==", video_id).order_by("created_at", direction=firestore.Query.DESCENDING)
        return [doc.to_dict() for doc in query.stream()]

    def get_pending_dubbing_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending dubbing jobs ready for worker pickup."""
        query = self.dubbing_jobs.where("status", "==", DubbingJobStatus.PENDING.value).limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]
        return sorted(jobs, key=lambda x: x.get("created_at") or 0)

    def delete_dubbing_job(self, job_id: str) -> None:
        """Delete a dubbing job record."""
        self.dubbing_jobs.document(job_id).delete()
        logger.info(f"[DubbingMixin] Deleted dubbing job {job_id}")
