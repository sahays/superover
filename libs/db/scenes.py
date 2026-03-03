"""Scene operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

from .enums import SceneJobStatus

logger = logging.getLogger(__name__)


class ScenesMixin:
    """Scene manifest, job, result, and prompt operations."""

    # === Scene Manifest Operations ===

    def create_manifest(self, video_id: str, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create scene processing manifest for a video."""
        manifest = {
            "video_id": video_id,
            "created_at": firestore.SERVER_TIMESTAMP,
            **manifest_data,
        }

        self.scene_manifests.document(video_id).set(manifest)
        logger.info(f"Created scene manifest for video: {video_id}")
        return manifest

    def get_manifest(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get scene manifest for a video."""
        doc = self.scene_manifests.document(video_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    # === Scene Result Operations ===

    def save_result(
        self,
        video_id: str,
        result_type: str,
        result_data: Dict[str, Any],
        scene_job_id: Optional[str] = None,
        gcs_path: Optional[str] = None,
    ) -> str:
        """Save scene analysis result."""
        result_doc = {
            "video_id": video_id,
            "result_type": result_type,
            "result_data": result_data,
            "gcs_path": gcs_path,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        if scene_job_id:
            result_doc["scene_job_id"] = scene_job_id

        doc_ref = self.scene_results.add(result_doc)
        logger.info(f"Saved scene result for video: {video_id}, type: {result_type}")
        return doc_ref[1].id

    def get_results_for_video(self, video_id: str, result_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all scene results for a video, optionally filtered by type."""
        query = self.scene_results.where("video_id", "==", video_id)

        if result_type:
            query = query.where("result_type", "==", result_type)

        return [doc.to_dict() for doc in query.stream()]

    def get_results_for_job(self, scene_job_id: str, result_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all scene results for a specific job, optionally filtered by type."""
        query = self.scene_results.where("scene_job_id", "==", scene_job_id)

        if result_type:
            query = query.where("result_type", "==", result_type)

        return [doc.to_dict() for doc in query.stream()]

    # === Scene Prompt Operations ===

    def save_prompt(
        self,
        video_id: str,
        chunk_index: int,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
    ) -> str:
        """Save a prompt used for scene analysis."""
        prompt_doc = {
            "video_id": video_id,
            "chunk_index": chunk_index,
            "prompt_text": prompt_text,
            "prompt_type": prompt_type,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        doc_ref = self.scene_prompts.add(prompt_doc)
        logger.info(f"Saved scene prompt for video: {video_id}, chunk: {chunk_index}")
        return doc_ref[1].id

    # === Scene Job Operations ===

    def create_scene_job(
        self,
        job_id: str,
        video_id: str,
        config: Dict[str, Any],
        prompt_id: str,
        prompt_text: str,
        prompt_type: str = "custom",
        prompt_name: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a scene analysis job."""
        job_data = {
            "job_id": job_id,
            "video_id": video_id,
            "status": SceneJobStatus.PENDING,
            "config": config,
            "prompt_id": prompt_id,
            "prompt_text": prompt_text,
            "prompt_type": prompt_type,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if prompt_name:
            job_data["prompt_name"] = prompt_name

        if response_schema is not None:
            job_data["response_schema"] = response_schema

        self.scene_jobs.document(job_id).set(job_data)
        logger.info(f"Created scene job: {job_id} for video: {video_id} with prompt: {prompt_id}")
        return self.get_scene_job(job_id)

    def get_scene_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get scene job by ID."""
        doc = self.scene_jobs.document(job_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_scene_job_status(
        self,
        job_id: str,
        status: SceneJobStatus,
        results: Optional[Dict[str, Any]] = None,
        stop_reason: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update scene job status and optionally store results."""
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if results:
            update_data["results"] = results

        if stop_reason:
            update_data["stop_reason"] = stop_reason

        if error_message:
            update_data["error_message"] = error_message

        self.scene_jobs.document(job_id).update(update_data)
        logger.info(f"Updated scene job {job_id} status to {status}")

    def list_scene_jobs_for_video(self, video_id: str, status: Optional[SceneJobStatus] = None) -> List[Dict[str, Any]]:
        """List all scene jobs for a video."""
        query = self.scene_jobs.where("video_id", "==", video_id)

        if status:
            query = query.where("status", "==", status)

        return [doc.to_dict() for doc in query.stream()]

    def get_pending_scene_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending scene jobs for worker processing."""
        query = self.scene_jobs.where("status", "==", SceneJobStatus.PENDING).limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    def delete_scene_job(self, job_id: str) -> None:
        """Delete a scene job."""
        self.scene_jobs.document(job_id).delete()
        logger.info(f"Deleted scene job: {job_id}")
