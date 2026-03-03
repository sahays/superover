"""Image job and result operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

from .enums import ImageJobStatus

logger = logging.getLogger(__name__)


class ImagesMixin:
    """Image job and result CRUD operations."""

    def create_image_job(
        self,
        job_id: str,
        video_id: str,
        config: Dict[str, Any],
        prompt_id: str,
        prompt_text: str,
        prompt_type: str = "image_adaptation",
        prompt_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an image adaptation job."""
        job_data = {
            "job_id": job_id,
            "video_id": video_id,
            "status": ImageJobStatus.PENDING,
            "config": config,
            "prompt_id": prompt_id,
            "prompt_text": prompt_text,
            "prompt_type": prompt_type,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "stop_reason": None,
        }

        if prompt_name:
            job_data["prompt_name"] = prompt_name

        self.image_jobs.document(job_id).set(job_data)
        logger.info(f"Created image job: {job_id} for asset: {video_id}")
        return self.get_image_job(job_id)

    def get_image_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get image job by ID."""
        doc = self.image_jobs.document(job_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_image_job_status(
        self,
        job_id: str,
        status: ImageJobStatus,
        results: Optional[Dict[str, Any]] = None,
        usage: Optional[Dict[str, Any]] = None,
        stop_reason: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update image job status and metadata."""
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if results:
            update_data["results"] = results
        if usage:
            update_data["usage"] = usage
        if stop_reason:
            update_data["stop_reason"] = stop_reason
        if error_message:
            update_data["error_message"] = error_message

        self.image_jobs.document(job_id).update(update_data)
        logger.info(f"Updated image job {job_id} status to {status}")

    def get_pending_image_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending image jobs for worker processing."""
        query = self.image_jobs.where("status", "==", ImageJobStatus.PENDING).limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    # === Image Result Operations ===

    def save_image_result(
        self,
        job_id: str,
        video_id: str,
        aspect_ratio: str,
        gcs_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save an individual image adaptation result."""
        result_doc = {
            "job_id": job_id,
            "video_id": video_id,
            "aspect_ratio": aspect_ratio,
            "gcs_path": gcs_path,
            "metadata": metadata or {},
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        doc_ref = self.image_results.add(result_doc)
        logger.info(f"Saved image result for job {job_id}, ratio {aspect_ratio}")
        return doc_ref[1].id

    def get_results_for_image_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all results for a specific image job."""
        query = self.image_results.where("job_id", "==", job_id)
        return [doc.to_dict() for doc in query.stream()]

    def list_image_jobs_for_video(self, video_id: str) -> List[Dict[str, Any]]:
        """List all image jobs for a specific video/image asset."""
        query = self.image_jobs.where("video_id", "==", video_id).order_by(
            "created_at", direction=firestore.Query.DESCENDING
        )
        return [doc.to_dict() for doc in query.stream()]

    def get_image_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific image result by document ID."""
        doc = self.image_results.document(result_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
