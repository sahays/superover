"""Media processing API routes."""

import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from api.models.schemas import (
    CreateMediaJobRequest,
    MediaJobResponse,
    MediaPresetResponse,
)
from api.middleware.rate_limit import rate_limit
from libs.database import get_db, MediaJobStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/media", tags=["media"])


def _is_media_file(video: dict) -> bool:
    """Return True if the video record represents an audio or video file."""
    ct = video.get("content_type", "")
    return ct.startswith("video/") or ct.startswith("audio/")


@router.post(
    "/jobs",
    response_model=MediaJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("media_processing"))],
)
async def create_media_job(request: Request, body: CreateMediaJobRequest):
    """
    Create a new media processing job.

    This creates a job that will be picked up by the media worker for processing.
    """
    try:
        db = get_db()

        # Verify video exists
        video = db.get_video(body.video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {body.video_id}",
            )

        # Create job
        job_id = str(uuid.uuid4())
        job_data = db.create_media_job(job_id=job_id, video_id=body.video_id, config=body.config.model_dump())

        return MediaJobResponse(**job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create media job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create media job: {str(e)}",
        )


@router.get("/jobs/{job_id}", response_model=MediaJobResponse)
async def get_media_job(job_id: str):
    """Get media job information by ID."""
    try:
        db = get_db()
        job = db.get_media_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media job not found: {job_id}",
            )

        return MediaJobResponse(**job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get media job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get media job: {str(e)}",
        )


@router.get("/jobs/video/{video_id}", response_model=List[MediaJobResponse])
async def list_media_jobs_for_video(video_id: str, status_filter: Optional[MediaJobStatus] = None):
    """List all media processing jobs for a video."""
    try:
        db = get_db()

        # Verify video exists
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}",
            )

        jobs = db.list_media_jobs_for_video(video_id, status=status_filter)
        return [MediaJobResponse(**job) for job in jobs]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list media jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list media jobs: {str(e)}",
        )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_job(job_id: str):
    """Delete a media processing job and all generated files (NOT the original video)."""
    try:
        from libs.storage import get_storage

        db = get_db()
        storage = get_storage()

        # Verify job exists
        job = db.get_media_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media job not found: {job_id}",
            )

        # Don't allow deleting jobs that are currently processing or transcoding
        if job["status"] in (MediaJobStatus.PROCESSING, MediaJobStatus.TRANSCODING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete job that is currently processing",
            )

        # Delete generated files from GCS (NOT the original video)
        files_deleted = []
        if job.get("results"):
            results = job["results"]

            # Delete compressed video
            if results.get("compressed_video_path"):
                try:
                    storage.delete_file(results["compressed_video_path"])
                    files_deleted.append("compressed video")
                    logger.info(f"Deleted compressed video: {results['compressed_video_path']}")
                except Exception as e:
                    logger.warning(f"Failed to delete compressed video: {e}")

            # Delete extracted audio
            if results.get("audio_path"):
                try:
                    storage.delete_file(results["audio_path"])
                    files_deleted.append("audio")
                    logger.info(f"Deleted audio: {results['audio_path']}")
                except Exception as e:
                    logger.warning(f"Failed to delete audio: {e}")

        # Delete job record from database
        db.delete_media_job(job_id)

        if files_deleted:
            logger.info(f"Deleted job {job_id} and files: {', '.join(files_deleted)}")
        else:
            logger.info(f"Deleted job {job_id} (no files to clean up)")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete media job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete media job: {str(e)}",
        )


@router.get("/videos")
async def list_all_videos(limit: int = 50):
    """
    List all uploaded videos (for media workflow).

    Returns ALL videos regardless of processing status - this is used by the media page
    to show videos available for media processing.
    """
    try:
        db = get_db()
        videos = db.list_videos(limit=limit)
        # Filter out non-audio/video files (e.g. images)
        videos = [v for v in videos if _is_media_file(v)]
        return videos

    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list videos: {str(e)}",
        )


@router.get("/presets", response_model=MediaPresetResponse)
async def get_media_presets():
    """Get available media processing presets and options."""
    return MediaPresetResponse(
        resolutions=["360p", "480p", "720p", "1080p", "1440p", "2160p"],
        audio_formats=["mp3", "aac", "wav"],
        audio_bitrates=["128k", "192k", "256k", "320k"],
        crf_range={"min": 0, "max": 51, "default": 23},
    )


@router.get("/videos-with-jobs")
async def get_all_videos_with_jobs():
    """Get all videos with their associated media processing jobs."""
    try:
        db = get_db()

        # Get all videos (exclude non-audio/video files)
        videos = [v for v in db.list_videos() if _is_media_file(v)]

        # For each video, get its media jobs
        videos_with_jobs = []
        for video in videos:
            video_id = video["video_id"]

            # Get all jobs for this video
            jobs = db.list_media_jobs_for_video(video_id)

            # Check if video has completed compressed versions
            has_compressed = any(
                job.get("status") == MediaJobStatus.COMPLETED and job.get("results", {}).get("compressed_video_path")
                for job in jobs
            )

            videos_with_jobs.append(
                {
                    "video_id": video_id,
                    "filename": video.get("filename"),
                    "gcs_path": video.get("gcs_path"),
                    "size_bytes": video.get("size_bytes"),
                    "metadata": video.get("metadata"),
                    "status": video.get("status"),  # Include the video's top-level status
                    "jobs": [MediaJobResponse(**job) for job in jobs],
                    "hasCompressed": has_compressed,
                }
            )

        return videos_with_jobs

    except Exception as e:
        logger.error(f"Failed to get videos with jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get videos with jobs: {str(e)}",
        )
