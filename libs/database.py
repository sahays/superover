"""
Firestore database module.
Works both locally and on Cloud Run.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from google.cloud import firestore
from config import settings

logger = logging.getLogger(__name__)


class MediaJobStatus(str, Enum):
    """Media processing job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SceneJobStatus(str, Enum):
    """Scene analysis job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FirestoreDB:
    """Firestore database operations."""

    def __init__(self):
        """Initialize Firestore client."""
        self.client = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database
        )
        # Core collections
        self.videos = self.client.collection("videos")

        # Scene workflow collections
        self.scene_manifests = self.client.collection("scene_manifests")
        self.scene_jobs = self.client.collection("scene_jobs")
        self.scene_results = self.client.collection("scene_results")
        self.scene_prompts = self.client.collection("scene_prompts")

        # Media workflow collections
        self.media_jobs = self.client.collection("media_jobs")

        # Prompt management collection
        self.prompts = self.client.collection("prompts")

    # === Video Operations ===

    def create_video(
        self,
        video_id: str,
        filename: str,
        gcs_path: str,
        content_type: str,
        size_bytes: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new video document.

        Args:
            video_id: Unique video ID
            filename: Original filename
            gcs_path: GCS path to uploaded video
            content_type: MIME type
            size_bytes: File size in bytes
            metadata: Additional metadata

        Returns:
            Created video document
        """
        # Auto-detect source_type from content_type
        source_type = 'audio' if content_type.startswith('audio/') else 'video'

        video_data = {
            "video_id": video_id,
            "filename": filename,
            "gcs_path": gcs_path,
            "content_type": content_type,
            "source_type": source_type,
            "size_bytes": size_bytes,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "metadata": metadata or {},
        }

        self.videos.document(video_id).set(video_data)
        logger.info(f"Created {source_type} document: {video_id}")

        # Fetch the document to get the actual timestamp values
        return self.get_video(video_id)

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video document by ID."""
        doc = self.videos.document(video_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_video_metadata(
        self,
        video_id: str,
        metadata: Dict[str, Any],
        merge: bool = True
    ) -> None:
        """
        Update video metadata.

        Args:
            video_id: Video ID
            metadata: Metadata to update
            merge: If True, merge with existing metadata. If False, replace entirely.
        """
        if merge:
            # Get existing metadata and merge
            video = self.get_video(video_id)
            if video and video.get("metadata"):
                merged_metadata = {**video["metadata"], **metadata}
            else:
                merged_metadata = metadata

            update_data = {
                "metadata": merged_metadata,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        else:
            update_data = {
                "metadata": metadata,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

        self.videos.document(video_id).update(update_data)
        logger.info(f"Updated metadata for video {video_id}")

    def update_video_audio_info(
        self,
        video_id: str,
        audio_info: Dict[str, Any]
    ) -> None:
        """Update video audio information."""
        update_data = {
            "audio_info": audio_info,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.videos.document(video_id).update(update_data)
        logger.info(f"Updated audio info for video {video_id}")

    def list_videos(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List all videos."""
        query = self.videos.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        return [doc.to_dict() for doc in query.stream()]

    # === Scene Manifest Operations ===

    def create_manifest(
        self,
        video_id: str,
        manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create scene processing manifest for a video.

        Args:
            video_id: Associated video ID
            manifest_data: Manifest containing chunks, audio, metadata

        Returns:
            Created manifest document
        """
        manifest = {
            "video_id": video_id,
            "created_at": firestore.SERVER_TIMESTAMP,
            **manifest_data
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
        gcs_path: Optional[str] = None
    ) -> str:
        """
        Save scene analysis result.

        Args:
            video_id: Associated video ID
            result_type: Type of result (scene_analysis, transcription, etc.)
            result_data: The analysis result
            scene_job_id: Optional parent scene job ID
            gcs_path: Optional GCS path to full result file

        Returns:
            Created result document ID
        """
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

    def get_results_for_video(
        self,
        video_id: str,
        result_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all scene results for a video, optionally filtered by type."""
        query = self.scene_results.where("video_id", "==", video_id)

        if result_type:
            query = query.where("result_type", "==", result_type)

        return [doc.to_dict() for doc in query.stream()]

    def get_results_for_job(
        self,
        scene_job_id: str,
        result_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
        prompt_type: str = "scene_analysis"
    ) -> str:
        """
        Save a prompt used for scene analysis.

        Args:
            video_id: Associated video ID
            chunk_index: Chunk index this prompt was used for
            prompt_text: The actual prompt text sent to Gemini
            prompt_type: Type of analysis (scene_analysis, transcription, etc.)

        Returns:
            Created prompt document ID
        """
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
    ) -> Dict[str, Any]:
        """
        Create a scene analysis job.

        Args:
            job_id: Unique job ID
            video_id: Associated video ID
            config: Processing configuration (chunk_duration, etc.)
            prompt_id: ID of the prompt being used
            prompt_text: The exact prompt text to be used for this job (embedded for reliability)
            prompt_type: Type of the prompt (embedded for display)
            prompt_name: Name of the prompt (embedded for display)

        Returns:
            Created job document
        """
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
        error_message: Optional[str] = None
    ) -> None:
        """Update scene job status and optionally store results."""
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if results:
            update_data["results"] = results

        if error_message:
            update_data["error_message"] = error_message

        self.scene_jobs.document(job_id).update(update_data)
        logger.info(f"Updated scene job {job_id} status to {status}")


    def list_scene_jobs_for_video(
        self,
        video_id: str,
        status: Optional[SceneJobStatus] = None
    ) -> List[Dict[str, Any]]:
        """List all scene jobs for a video."""
        query = self.scene_jobs.where("video_id", "==", video_id)

        if status:
            query = query.where("status", "==", status)

        return [doc.to_dict() for doc in query.stream()]

    def get_pending_scene_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending scene jobs for worker processing."""
        query = (
            self.scene_jobs
            .where("status", "==", SceneJobStatus.PENDING)
            .limit(limit)
        )
        jobs = [doc.to_dict() for doc in query.stream()]
        # Sort by created_at in memory to avoid needing a composite index
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    def delete_scene_job(self, job_id: str) -> None:
        """Delete a scene job."""
        self.scene_jobs.document(job_id).delete()
        logger.info(f"Deleted scene job: {job_id}")

    # === Media Job Operations ===

    def create_media_job(
        self,
        job_id: str,
        video_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a media processing job.

        Args:
            job_id: Unique job ID
            video_id: Associated video ID
            config: Processing configuration

        Returns:
            Created job document
        """
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
        error_message: Optional[str] = None
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

    def list_media_jobs_for_video(
        self,
        video_id: str,
        status: Optional[MediaJobStatus] = None
    ) -> List[Dict[str, Any]]:
        """List all media jobs for a video."""
        query = self.media_jobs.where("video_id", "==", video_id)

        if status:
            query = query.where("status", "==", status)

        return [doc.to_dict() for doc in query.stream()]

    def get_pending_media_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending media jobs for worker processing."""
        query = (
            self.media_jobs
            .where("status", "==", MediaJobStatus.PENDING)
            .limit(limit)
        )
        jobs = [doc.to_dict() for doc in query.stream()]
        # Sort by created_at in memory to avoid needing a composite index
        return sorted(jobs, key=lambda x: x.get("created_at", 0))

    def delete_media_job(self, job_id: str) -> None:
        """Delete a media job."""
        self.media_jobs.document(job_id).delete()
        logger.info(f"Deleted media job: {job_id}")

    # === Prompt Management Operations ===

    def create_prompt(
        self,
        name: str,
        type: str,
        prompt_text: str,
    ) -> Dict[str, Any]:
        """
        Create a new prompt document with auto-generated ID.

        Args:
            name: User-friendly name for the prompt
            type: Type of the prompt (scene_analysis, object_identification, etc.)
            prompt_text: The full prompt text

        Returns:
            Created prompt document
        """
        import uuid

        prompt_id = str(uuid.uuid4())
        prompt_data = {
            "prompt_id": prompt_id,
            "name": name,
            "type": type,
            "prompt_text": prompt_text,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.prompts.document(prompt_id).set(prompt_data)
        logger.info(f"Created prompt: {prompt_id} ({name}) of type {type}")
        return self.get_prompt(prompt_id)

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a prompt document by its ID."""
        doc = self.prompts.document(prompt_id).get()
        if doc.exists:
            data = doc.to_dict()
            # Backward compatibility: default to 'custom' if type is missing
            if 'type' not in data:
                data['type'] = 'custom'
            # Backward compatibility: use prompt_name if name is missing (old schema)
            if 'name' not in data and 'prompt_name' in data:
                data['name'] = data['prompt_name']
            # Backward compatibility: set a default name if still missing
            if 'name' not in data:
                data['name'] = f"Prompt {data.get('prompt_id', 'unknown')[:8]}"
            return data
        return None

    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompt documents ordered by creation date."""
        query = self.prompts.order_by("created_at", direction=firestore.Query.DESCENDING)
        prompts = []
        for doc in query.stream():
            data = doc.to_dict()
            # Backward compatibility: default to 'custom' if type is missing
            if 'type' not in data:
                data['type'] = 'custom'
            # Backward compatibility: use prompt_name if name is missing (old schema)
            if 'name' not in data and 'prompt_name' in data:
                data['name'] = data['prompt_name']
            # Backward compatibility: set a default name if still missing
            if 'name' not in data:
                data['name'] = f"Prompt {data.get('prompt_id', 'unknown')[:8]}"
            prompts.append(data)
        return prompts

    def update_prompt(
        self,
        prompt_id: str,
        name: Optional[str] = None,
        type: Optional[str] = None,
        prompt_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update a prompt document.

        Args:
            prompt_id: ID of the prompt to update
            name: New name (optional)
            type: New type (optional)
            prompt_text: New prompt text (optional)

        Returns:
            Updated prompt document or None if not found
        """
        prompt_ref = self.prompts.document(prompt_id)
        if not prompt_ref.get().exists:
            return None

        update_data = {"updated_at": firestore.SERVER_TIMESTAMP}

        if name is not None:
            update_data["name"] = name
        if type is not None:
            update_data["type"] = type
        if prompt_text is not None:
            update_data["prompt_text"] = prompt_text

        if len(update_data) == 1:  # Only updated_at
            raise ValueError("At least one field (name, type, or prompt_text) must be provided")

        prompt_ref.update(update_data)
        logger.info(f"Updated prompt: {prompt_id}")
        return self.get_prompt(prompt_id)

    def delete_prompt(self, prompt_id: str) -> None:
        """Delete a prompt document."""
        self.prompts.document(prompt_id).delete()
        logger.info(f"Deleted prompt: {prompt_id}")

    def count_jobs_using_prompt(self, prompt_id: str) -> int:
        """Count how many scene jobs are using this prompt."""
        query = self.scene_jobs.where("prompt_id", "==", prompt_id)
        return len(list(query.stream()))




# Singleton instance
_db_instance: Optional[FirestoreDB] = None


def get_db() -> FirestoreDB:
    """Get or create Firestore DB instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FirestoreDB()
    return _db_instance
