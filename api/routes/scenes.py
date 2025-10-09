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
    SceneAnalysisRequest,
    SceneAnalysisJobResponse,
    ManifestResponse,
    ResultResponse,
)
from libs.storage import get_storage
from libs.database import get_db, VideoStatus, TaskStatus

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
            bucket_type="uploads"
        )

        return SignedUrlResponse(
            signed_url=signed_url,
            gcs_path=gcs_path,
            expires_in_minutes=15
        )

    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {str(e)}"
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
            metadata=request.metadata
        )

        return VideoResponse(**video_data)

    except Exception as e:
        logger.error(f"Failed to create video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create video: {str(e)}"
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
                detail=f"Video not found: {video_id}"
            )

        return VideoResponse(**video)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video: {str(e)}"
        )


@router.get("", response_model=List[VideoResponse])
async def list_videos(
    limit: int = 50,
    status_filter: VideoStatus = None
):
    """
    List videos that have scene jobs.

    This endpoint only returns videos that have been through the scene workflow,
    not just uploaded/media-processed videos.
    """
    try:
        db = get_db()

        # Get all scene jobs to find videos with scene data
        job_docs = db.scene_jobs.limit(limit * 2).stream()  # Get more jobs since multiple per video
        video_ids_with_jobs = set()
        for doc in job_docs:
            job = doc.to_dict()
            if job.get("video_id"):
                video_ids_with_jobs.add(job["video_id"])

        # Get videos that have scene jobs
        videos = []
        for video_id in video_ids_with_jobs:
            video = db.get_video(video_id)
            if video:
                # Apply status filter if provided
                if status_filter is None or video.get("status") == status_filter:
                    videos.append(video)

        # Sort by created_at descending
        videos.sort(key=lambda v: v.get("created_at", 0), reverse=True)

        # Limit results
        videos = videos[:limit]

        return [VideoResponse(**v) for v in videos]

    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list videos: {str(e)}"
        )


@router.post("/{video_id}/process", response_model=ProcessingJobResponse)
async def process_video(video_id: str, request: ProcessVideoRequest):
    """
    Start scene processing (compression, chunking, audio extraction).

    This creates a scene job and task that will be picked up by a worker.
    """
    try:
        db = get_db()

        # Verify video exists
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )

        # Update video status to first processing step
        db.update_video_status(video_id, VideoStatus.EXTRACTING_METADATA)

        # Create scene job
        job_id = str(uuid.uuid4())
        job_data = db.create_scene_job(
            job_id=job_id,
            video_id=video_id,
            config={
                "compressed_video_path": request.compressed_video_path,
                "chunk_duration": request.chunk_duration,
                "chunk": request.chunk,
            }
        )

        # Create processing task linked to the job
        task_id = str(uuid.uuid4())
        task_data = db.create_task(
            task_id=task_id,
            video_id=video_id,
            task_type="scene_processing",
            input_data={
                "compressed_video_path": request.compressed_video_path,
                "chunk_duration": request.chunk_duration,
                "chunk": request.chunk,
            },
            scene_job_id=job_id
        )

        # Add task to scene job
        db.add_task_to_scene_job(job_id, task_id)

        return ProcessingJobResponse(
            video_id=video_id,
            status="processing",
            message=f"Scene processing started. Job ID: {job_id}, Task ID: {task_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}"
        )


@router.post("/{video_id}/scene-analysis", response_model=SceneAnalysisJobResponse)
async def analyze_scenes(video_id: str, request: SceneAnalysisRequest):
    """
    Start Gemini scene analysis on processed video.

    Creates scene analysis tasks for each chunk/scene type.
    """
    try:
        db = get_db()

        # Verify video exists and is processed
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scene not found: {video_id}"
            )

        if video["status"] != VideoStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scene must be completed before analysis. Current status: {video['status']}"
            )

        # Get manifest
        manifest = db.get_manifest(video_id)
        if not manifest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manifest not found for scene: {video_id}"
            )

        # Update video status
        db.update_video_status(video_id, VideoStatus.ANALYZING)

        # Create scene analysis tasks for each chunk
        task_ids = []
        chunks = manifest.get("chunks", {}).get("items", [])

        for chunk in chunks:
            for scene_type in request.scene_types:
                task_id = str(uuid.uuid4())
                db.create_task(
                    task_id=task_id,
                    video_id=video_id,
                    task_type=f"scene_{scene_type}",
                    input_data={
                        "chunk": chunk,
                        "scene_type": scene_type,
                    }
                )
                task_ids.append(task_id)

        return SceneAnalysisJobResponse(
            video_id=video_id,
            task_ids=task_ids,
            status="analyzing",
            message=f"Created {len(task_ids)} scene analysis tasks"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start scene analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scene analysis: {str(e)}"
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
                detail=f"Manifest not found for video: {video_id}"
            )

        return ManifestResponse(**manifest)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get manifest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get manifest: {str(e)}"
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
                created_at=r.get("created_at")
            )
            for i, r in enumerate(results)
        ]

    except Exception as e:
        logger.error(f"Failed to get results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get results: {str(e)}"
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
                detail=f"Scene not found: {video_id}"
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

        # Reset video status to uploaded (preserving the video record and original file)
        db.update_video_status(video_id, VideoStatus.UPLOADED)

        # Delete manifest
        db.scene_manifests.document(video_id).delete()

        # Delete all scene processing tasks for this video
        tasks = db.list_tasks_for_video(video_id)
        tasks_deleted = 0
        for task in tasks:
            task_id = task.get("task_id")
            if task_id:
                try:
                    db.scene_tasks.document(task_id).delete()
                    tasks_deleted += 1
                    logger.info(f"Deleted task: {task_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete task {task_id}: {e}")

        if tasks_deleted > 0:
            logger.info(f"Deleted {tasks_deleted} tasks for video {video_id}")

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

        # Delete all prompts for this video (which are currently stored per chunk - will be refactored)
        prompts_query = db.scene_prompts.where("video_id", "==", video_id)
        prompts_deleted = 0
        for doc in prompts_query.stream():
            try:
                doc.reference.delete()
                prompts_deleted += 1
                logger.info(f"Deleted prompt: {doc.id}")
            except Exception as e:
                logger.warning(f"Failed to delete prompt {doc.id}: {e}")

        if prompts_deleted > 0:
            logger.info(f"Deleted {prompts_deleted} prompts for video {video_id}")

        logger.info(f"Deleted scene analysis data for {video_id}, preserved source video at {video.get('gcs_path')}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scene: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scene: {str(e)}"
        )
