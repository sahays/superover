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


class VideoStatus(str, Enum):
    """Video processing status."""
    UPLOADED = "uploaded"
    EXTRACTING_METADATA = "extracting_metadata"
    EXTRACTING_AUDIO = "extracting_audio"
    COMPRESSING = "compressing"
    CHUNKING = "chunking"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """Analysis task status."""
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
        self.videos = self.client.collection("videos")
        self.manifests = self.client.collection("manifests")
        self.tasks = self.client.collection("analysis_tasks")
        self.results = self.client.collection("results")
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
        video_data = {
            "video_id": video_id,
            "filename": filename,
            "gcs_path": gcs_path,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "status": VideoStatus.UPLOADED,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "metadata": metadata or {},
        }

        self.videos.document(video_id).set(video_data)
        logger.info(f"Created video document: {video_id}")

        # Fetch the document to get the actual timestamp values
        return self.get_video(video_id)

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video document by ID."""
        doc = self.videos.document(video_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_video_status(
        self,
        video_id: str,
        status: VideoStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Update video status."""
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if error_message:
            update_data["error_message"] = error_message

        self.videos.document(video_id).update(update_data)
        logger.info(f"Updated video {video_id} status to {status}")

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
        limit: int = 50,
        status: Optional[VideoStatus] = None
    ) -> List[Dict[str, Any]]:
        """List videos, optionally filtered by status."""
        query = self.videos.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)

        if status:
            query = query.where("status", "==", status)

        return [doc.to_dict() for doc in query.stream()]

    # === Manifest Operations ===

    def create_manifest(
        self,
        video_id: str,
        manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create processing manifest for a video.

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

        self.manifests.document(video_id).set(manifest)
        logger.info(f"Created manifest for video: {video_id}")
        return manifest

    def get_manifest(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get manifest for a video."""
        doc = self.manifests.document(video_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    # === Task Operations ===

    def create_task(
        self,
        task_id: str,
        video_id: str,
        task_type: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create an analysis task.

        Args:
            task_id: Unique task ID
            video_id: Associated video ID
            task_type: Type of task (scene_analysis, transcription, moderation, etc.)
            input_data: Task-specific input data

        Returns:
            Created task document
        """
        task_data = {
            "task_id": task_id,
            "video_id": video_id,
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "input_data": input_data,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        self.tasks.document(task_id).set(task_data)
        logger.info(f"Created task: {task_id} for video: {video_id}")
        return task_data

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID."""
        doc = self.tasks.document(task_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update task status and optionally store result."""
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if result_data:
            update_data["result_data"] = result_data

        if error_message:
            update_data["error_message"] = error_message

        self.tasks.document(task_id).update(update_data)
        logger.info(f"Updated task {task_id} status to {status}")

    def list_tasks_for_video(
        self,
        video_id: str,
        status: Optional[TaskStatus] = None
    ) -> List[Dict[str, Any]]:
        """List all tasks for a video."""
        query = self.tasks.where("video_id", "==", video_id)

        if status:
            query = query.where("status", "==", status)

        return [doc.to_dict() for doc in query.stream()]

    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending tasks for worker processing."""
        query = (
            self.tasks
            .where("status", "==", TaskStatus.PENDING)
            .limit(limit)
        )
        tasks = [doc.to_dict() for doc in query.stream()]
        # Sort by created_at in memory to avoid needing a composite index
        return sorted(tasks, key=lambda x: x.get("created_at", 0))

    # === Result Operations ===

    def save_result(
        self,
        video_id: str,
        result_type: str,
        result_data: Dict[str, Any],
        gcs_path: Optional[str] = None
    ) -> str:
        """
        Save analysis result.

        Args:
            video_id: Associated video ID
            result_type: Type of result (scene_analysis, transcription, etc.)
            result_data: The analysis result
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

        doc_ref = self.results.add(result_doc)
        logger.info(f"Saved result for video: {video_id}, type: {result_type}")
        return doc_ref[1].id

    def get_results_for_video(
        self,
        video_id: str,
        result_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all results for a video, optionally filtered by type."""
        query = self.results.where("video_id", "==", video_id)

        if result_type:
            query = query.where("result_type", "==", result_type)

        return [doc.to_dict() for doc in query.stream()]

    # === Prompt Operations ===

    def save_prompt(
        self,
        video_id: str,
        chunk_index: int,
        prompt_text: str,
        prompt_type: str = "scene_analysis"
    ) -> str:
        """
        Save a prompt used for analysis.

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

        doc_ref = self.prompts.add(prompt_doc)
        logger.info(f"Saved prompt for video: {video_id}, chunk: {chunk_index}")
        return doc_ref[1].id

    # === Utility Methods ===

    def watch_pending_tasks(self, callback):
        """
        Watch for new pending tasks (for worker).
        Callback is called whenever a new pending task is created.

        Args:
            callback: Function to call with new task data
        """
        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == "ADDED":
                    task_data = change.document.to_dict()
                    if task_data.get("status") == TaskStatus.PENDING:
                        callback(task_data)

        query = self.tasks.where("status", "==", TaskStatus.PENDING)
        query.on_snapshot(on_snapshot)
        logger.info("Started watching for pending tasks")


# Singleton instance
_db_instance: Optional[FirestoreDB] = None


def get_db() -> FirestoreDB:
    """Get or create Firestore DB instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FirestoreDB()
    return _db_instance
