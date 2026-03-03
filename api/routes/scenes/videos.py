"""Video CRUD and scene deletion handlers."""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import CreateVideoRequest, VideoResponse
from libs.database import get_db, SceneJobStatus
from libs.storage import get_storage

logger = logging.getLogger(__name__)


def register_video_routes(router: APIRouter) -> None:
    """Register video-related routes on the given router."""

    @router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
    async def create_video(request: CreateVideoRequest):
        """Create a video record after successful upload."""
        try:
            db = get_db()
            video_id = request.gcs_path.split("/")[-1].split(".")[0]

            video_data = db.create_video(
                video_id=video_id,
                filename=request.filename,
                gcs_path=request.gcs_path,
                content_type=request.content_type,
                size_bytes=request.size_bytes,
                metadata=request.metadata,
            )

            return VideoResponse(**video_data)

        except Exception as e:
            logger.error(f"Failed to create video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create video: {str(e)}",
            )

    @router.get("/{video_id}", response_model=VideoResponse)
    async def get_video(video_id: str):
        """Get video information by ID."""
        try:
            db = get_db()
            video = db.get_video(video_id)

            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video not found: {video_id}",
                )

            return VideoResponse(**video)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get video: {str(e)}",
            )

    @router.get("/{video_id}/playback-url")
    async def get_playback_url(video_id: str):
        """Get a signed download URL for video playback."""
        try:
            db = get_db()
            video = db.get_video(video_id)

            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video not found: {video_id}",
                )

            gcs_path = video.get("gcs_path")
            if not gcs_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video has no GCS path: {video_id}",
                )

            storage = get_storage()
            content_type = video.get("content_type", "video/mp4")
            signed_url = storage.generate_signed_download_url(
                gcs_path=gcs_path,
                expiration_minutes=60,
                response_content_type=content_type,
            )

            return {"signed_url": signed_url, "content_type": content_type}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get playback URL for {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get playback URL: {str(e)}",
            )

    @router.get("", response_model=List[VideoResponse])
    async def list_videos(limit: int = 50, status_filter: SceneJobStatus = None):
        """List scene jobs with their associated video information."""
        try:
            db = get_db()
            query = db.scene_jobs

            if status_filter:
                query = query.where("status", "==", status_filter.value)

            job_docs = query.order_by("created_at", direction="DESCENDING").limit(limit).stream()

            videos_with_jobs = []
            for doc in job_docs:
                job = doc.to_dict()
                video = db.get_video(job["video_id"])
                if video:
                    response_data = {
                        "video_id": video["video_id"],
                        "filename": video["filename"],
                        "gcs_path": video["gcs_path"],
                        "status": job["status"],
                        "created_at": job["created_at"],
                        "updated_at": job["updated_at"],
                        "metadata": video.get("metadata", {}),
                        "error_message": job.get("error_message"),
                    }
                    videos_with_jobs.append(response_data)

            return [VideoResponse(**v) for v in videos_with_jobs]

        except Exception as e:
            logger.error(f"Failed to list videos: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list videos: {str(e)}",
            )

    @router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_scene(video_id: str):
        """Delete scene analysis data but preserve the original source video."""
        try:
            db = get_db()
            storage = get_storage()

            video = db.get_video(video_id)
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scene not found: {video_id}",
                )

            manifest = db.get_manifest(video_id)
            if manifest:
                if manifest.get("compressed_path"):
                    storage.delete_file(manifest["compressed_path"])
                    logger.info(f"Deleted compressed video: {manifest['compressed_path']}")

                for chunk in manifest.get("chunks", []):
                    if chunk.get("gcs_path"):
                        storage.delete_file(chunk["gcs_path"])
                        logger.info(f"Deleted chunk: {chunk['gcs_path']}")

                if manifest.get("audio_path"):
                    storage.delete_file(manifest["audio_path"])
                    logger.info(f"Deleted audio: {manifest['audio_path']}")

            db.scene_manifests.document(video_id).delete()

            scene_jobs = db.list_scene_jobs_for_video(video_id)
            jobs_deleted = 0
            for job in scene_jobs:
                job_id = job.get("job_id")
                if job_id:
                    try:
                        db.scene_jobs.document(job_id).delete()
                        jobs_deleted += 1
                        logger.info(f"Deleted scene job: {job_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete scene job {job_id}: {e}")

            if jobs_deleted > 0:
                logger.info(f"Deleted {jobs_deleted} scene jobs for video {video_id}")

            query = db.scene_results.where("video_id", "==", video_id)
            deleted_count = 0
            for doc in query.stream():
                try:
                    doc.reference.delete()
                    deleted_count += 1
                    logger.info(f"Deleted result: {doc.id}")
                except Exception as e:
                    logger.warning(f"Failed to delete result {doc.id}: {e}")

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} results for video {video_id}")

            db.delete_scene_job(video_id)
            logger.info(
                f"Deleted scene analysis data for {video_id}, preserved source video at {video.get('gcs_path')}"
            )
            return None

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete scene: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete scene: {str(e)}",
            )
