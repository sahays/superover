"""Scene management API routes."""

import uuid
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import (
    SignedUrlRequest,
    SignedUrlResponse,
    CreateVideoRequest,
    VideoResponse,
    ProcessVideoRequest,
    ProcessingJobResponse,
    SceneJobResponse,
    ManifestResponse,
    ResultResponse,
)
from libs.storage import get_storage
from libs.database import get_db, SceneJobStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.post("/signed-url", response_model=SignedUrlResponse)
async def get_signed_upload_url(request: SignedUrlRequest):
    """
    Generate a signed URL for direct video upload to GCS.

    The frontend can use this URL to upload videos directly to GCS
    without going through the API server.
    """
    try:
        storage = get_storage()

        # Generate unique filename
        file_ext = request.filename.split(".")[-1] if "." in request.filename else "mp4"
        unique_filename = f"{uuid.uuid4()}.{file_ext}"

        signed_url, gcs_path = storage.generate_signed_upload_url(
            filename=unique_filename,
            content_type=request.content_type,
            bucket_type="uploads",
        )

        return SignedUrlResponse(signed_url=signed_url, gcs_path=gcs_path, expires_in_minutes=15)

    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {str(e)}",
        )


@router.post("/context/signed-url", response_model=SignedUrlResponse)
async def get_context_signed_upload_url(request: SignedUrlRequest):
    """
    Generate a signed URL for direct context file upload to GCS.

    Context files (text, images, etc.) are uploaded to a separate path
    for use with scene analysis jobs.
    """
    try:
        storage = get_storage()

        # Generate unique filename for context file
        file_ext = request.filename.split(".")[-1] if "." in request.filename else "txt"
        unique_filename = f"context/{uuid.uuid4()}.{file_ext}"

        signed_url, gcs_path = storage.generate_signed_upload_url(
            filename=unique_filename,
            content_type=request.content_type,
            bucket_type="processed",  # Store in processed bucket
        )

        return SignedUrlResponse(signed_url=signed_url, gcs_path=gcs_path, expires_in_minutes=15)

    except Exception as e:
        logger.error(f"Failed to generate context signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate context signed URL: {str(e)}",
        )


@router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(request: CreateVideoRequest):
    """
    Create a video record after successful upload.

    Call this after uploading the video file using the signed URL.
    """
    try:
        db = get_db()

        # Extract video ID from GCS path
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


@router.get("/jobs/{job_id}/results", response_model=List[ResultResponse])
async def get_results_for_job(job_id: str, result_type: str = None):
    """Get analysis results for a specific scene job."""
    try:
        db = get_db()

        # Verify job exists
        job = db.get_scene_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scene job not found: {job_id}",
            )

        results = db.get_results_for_job(job_id, result_type=result_type)

        return [
            ResultResponse(
                result_id=str(i),
                video_id=r["video_id"],
                result_type=r["result_type"],
                result_data=r["result_data"],
                gcs_path=r.get("gcs_path"),
                created_at=r.get("created_at"),
            )
            for i, r in enumerate(results)
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get results for job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get results for job: {str(e)}",
        )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene_job_endpoint(job_id: str):
    """Delete a scene job and its results (including stuck/orphaned jobs)."""
    try:
        db = get_db()

        job = db.get_scene_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scene job not found: {job_id}",
            )

        video_id = job["video_id"]
        status_info = f"status={job['status']}"

        # Delete associated results
        query = db.scene_results.where("scene_job_id", "==", job_id)
        for doc in query.stream():
            doc.reference.delete()

        # Delete the job
        db.delete_scene_job(job_id)

        logger.info(f"Deleted scene job {job_id} for video {video_id} ({status_info})")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scene job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scene job: {str(e)}",
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


@router.get("", response_model=List[VideoResponse])
async def list_videos(limit: int = 50, status_filter: SceneJobStatus = None):
    """
    List scene jobs with their associated video information.
    """
    try:
        db = get_db()

        # Base query for scene jobs
        query = db.scene_jobs

        # Apply status filter if provided
        if status_filter:
            query = query.where("status", "==", status_filter.value)

        # Order by creation date and limit results
        job_docs = query.order_by("created_at", direction="DESCENDING").limit(limit).stream()

        # Combine job data with video data
        videos_with_jobs = []
        for doc in job_docs:
            job = doc.to_dict()
            video = db.get_video(job["video_id"])
            if video:
                # Combine video info with job status
                response_data = {
                    "video_id": video["video_id"],
                    "filename": video["filename"],
                    "gcs_path": video["gcs_path"],
                    "status": job["status"],  # Use job status as the primary status
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


@router.post("/{video_id}/process", response_model=ProcessingJobResponse)
async def process_video(video_id: str, request: ProcessVideoRequest):
    """
    Start scene processing with user-selected prompt.

    This creates a scene job that will be picked up by a worker.
    """
    try:
        db = get_db()

        logger.info("=== process_video API called ===")
        logger.info(f"video_id: {video_id}")
        logger.info(f"request.chunk_duration: {request.chunk_duration} (type: {type(request.chunk_duration).__name__})")
        logger.info(f"request.chunk: {request.chunk}")
        logger.info(f"request.compressed_video_path: {request.compressed_video_path}")
        logger.info(f"request.prompt_id: {request.prompt_id}")

        # Verify video exists
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}",
            )

        # Get the specified prompt (REQUIRED)
        prompt = db.get_prompt(request.prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {request.prompt_id}. Please select a valid prompt.",
            )

        # Create scene job with prompt_id, embedded prompt_text, prompt_type, and prompt_name
        job_id = str(uuid.uuid4())

        config = {
            "compressed_video_path": request.compressed_video_path,
            "chunk_duration": request.chunk_duration,
            "chunk": request.chunk,
        }

        # Add context items to config if provided
        if request.context_items:
            config["context_items"] = [item.dict() for item in request.context_items]
            logger.info(f"Added {len(request.context_items)} context items to job config")

        logger.info(f"Creating job with config: {config}")

        db.create_scene_job(
            job_id=job_id,
            video_id=video_id,
            config=config,
            prompt_id=request.prompt_id,  # Store prompt reference
            prompt_text=prompt["prompt_text"],  # Embed for reliability
            prompt_type=prompt.get("type", "custom"),  # Embed prompt type for display
            prompt_name=prompt.get("name"),  # Embed prompt name for display
        )

        return ProcessingJobResponse(
            video_id=video_id,
            status="pending",
            message=f"Scene processing job created. Job ID: {job_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}",
        )


@router.get("/jobs", response_model=List[SceneJobResponse])
async def list_scene_jobs(limit: int = 50, status_filter: SceneJobStatus = None):
    """List all scene jobs."""
    try:
        db = get_db()

        if status_filter:
            jobs = [j for j in db.list_scene_jobs_for_video("", status=status_filter) if True]
            # Need to query all jobs - let's use a different approach
            query = db.scene_jobs.where("status", "==", status_filter.value)
        else:
            query = db.scene_jobs

        query = query.order_by("created_at", direction="DESCENDING").limit(limit)
        jobs = [doc.to_dict() for doc in query.stream()]

        return [SceneJobResponse(**job) for job in jobs]

    except Exception as e:
        logger.error(f"Failed to list scene jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scene jobs: {str(e)}",
        )


@router.get("/jobs/{job_id}", response_model=SceneJobResponse)
async def get_scene_job(job_id: str):
    """Get scene job by ID."""
    try:
        db = get_db()
        job = db.get_scene_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scene job not found: {job_id}",
            )

        return SceneJobResponse(**job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scene job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scene job: {str(e)}",
        )


@router.get("/{video_id}/manifest", response_model=ManifestResponse)
async def get_manifest(video_id: str):
    """Get processing manifest for a video."""
    try:
        db = get_db()
        manifest = db.get_manifest(video_id)

        if not manifest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manifest not found for video: {video_id}",
            )

        # Ensure required fields exist with defaults
        manifest_data = {
            "video_id": manifest.get("video_id", video_id),
            "version": manifest.get("version", "1.0"),
            "original": manifest.get("original", {}),
            "compressed": manifest.get("compressed"),
            "chunks": manifest.get("chunks"),
            "audio": manifest.get("audio"),
            "processing": manifest.get("processing"),
        }

        return ManifestResponse(**manifest_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get manifest for {video_id}: {e}")
        logger.error(f"Manifest data: {manifest if 'manifest' in locals() else 'not loaded'}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get manifest: {str(e)}",
        )


@router.get("/{video_id}/results", response_model=List[ResultResponse])
async def get_results(video_id: str, result_type: str = None):
    """Get analysis results for a video."""
    try:
        db = get_db()
        results = db.get_results_for_video(video_id, result_type=result_type)

        return [
            ResultResponse(
                result_id=str(i),
                video_id=r["video_id"],
                result_type=r["result_type"],
                result_data=r["result_data"],
                gcs_path=r.get("gcs_path"),
                created_at=r.get("created_at"),
            )
            for i, r in enumerate(results)
        ]

    except Exception as e:
        logger.error(f"Failed to get results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get results: {str(e)}",
        )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(video_id: str):
    """
    Delete scene analysis data (chunks, results, tasks) but preserve the original source video.

    This allows the source video to remain available for other workflows (media processing, etc.)
    """
    try:
        db = get_db()
        storage = get_storage()

        # Get video to verify it exists
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scene not found: {video_id}",
            )

        # Delete manifest and scene-processed files (NOT the original source video)
        manifest = db.get_manifest(video_id)
        if manifest:
            # Delete compressed video from scene workflow
            if manifest.get("compressed_path"):
                storage.delete_file(manifest["compressed_path"])
                logger.info(f"Deleted compressed video: {manifest['compressed_path']}")

            # Delete chunks from scene workflow
            for chunk in manifest.get("chunks", []):
                if chunk.get("gcs_path"):
                    storage.delete_file(chunk["gcs_path"])
                    logger.info(f"Deleted chunk: {chunk['gcs_path']}")

            # Delete audio from scene workflow
            if manifest.get("audio_path"):
                storage.delete_file(manifest["audio_path"])
                logger.info(f"Deleted audio: {manifest['audio_path']}")

        # Delete manifest
        db.scene_manifests.document(video_id).delete()

        # Delete all scene jobs for this video
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

        # Delete all scene analysis results for this video
        # Note: Results use auto-generated IDs, so we need to query and delete by document reference
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

        # Delete the scene job itself
        db.delete_scene_job(video_id)
        logger.info(f"Deleted scene job for video {video_id}")

        logger.info(f"Deleted scene analysis data for {video_id}, preserved source video at {video.get('gcs_path')}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scene: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scene: {str(e)}",
        )
