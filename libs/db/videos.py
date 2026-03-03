"""Video operations mixin for FirestoreDB."""

import logging
from typing import Optional, Dict, Any, List
from google.cloud import firestore

logger = logging.getLogger(__name__)


class VideosMixin:
    """Video CRUD operations."""

    def create_video(
        self,
        video_id: str,
        filename: str,
        gcs_path: str,
        content_type: str,
        size_bytes: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new video document."""
        source_type = "audio" if content_type.startswith("audio/") else "video"

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

        return self.get_video(video_id)

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video document by ID."""
        doc = self.videos.document(video_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_video_metadata(self, video_id: str, metadata: Dict[str, Any], merge: bool = True) -> None:
        """Update video metadata."""
        if merge:
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

    def update_video_audio_info(self, video_id: str, audio_info: Dict[str, Any]) -> None:
        """Update video audio information."""
        update_data = {
            "audio_info": audio_info,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.videos.document(video_id).update(update_data)
        logger.info(f"Updated audio info for video {video_id}")

    def list_videos(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all videos."""
        query = self.videos.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        return [doc.to_dict() for doc in query.stream()]
