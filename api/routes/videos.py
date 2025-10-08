"""Video management API routes."""
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
    AnalyzeVideoRequest,
    AnalysisJobResponse,
    ManifestResponse,
    ResultResponse,
)
from libs.storage import get_storage
from libs.database import get_db, VideoStatus, TaskStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


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
    """List all videos, optionally filtered by status."""
    try:
        db = get_db()
        videos = db.list_videos(limit=limit, status=status_filter)
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
    Start video processing (compression, chunking, audio extraction).

    This creates a processing task that will be picked up by a worker.
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

        # Create processing task
        task_id = str(uuid.uuid4())
        task_data = db.create_task(
            task_id=task_id,
            video_id=video_id,
            task_type="video_processing",
            input_data={
                "compress": request.compress,
                "chunk": request.chunk,
                "extract_audio": request.extract_audio,
            }
        )

        return ProcessingJobResponse(
            video_id=video_id,
            status="processing",
            message=f"Video processing started. Task ID: {task_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}"
        )


@router.post("/{video_id}/analyze", response_model=AnalysisJobResponse)
async def analyze_video(video_id: str, request: AnalyzeVideoRequest):
    """
    Start Gemini analysis on processed video.

    Creates analysis tasks for each chunk/analysis type.
    """
    try:
        db = get_db()

        # Verify video exists and is processed
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )

        if video["status"] != VideoStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video must be completed before analysis. Current status: {video['status']}"
            )

        # Get manifest
        manifest = db.get_manifest(video_id)
        if not manifest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manifest not found for video: {video_id}"
            )

        # Update video status
        db.update_video_status(video_id, VideoStatus.ANALYZING)

        # Create analysis tasks for each chunk
        task_ids = []
        chunks = manifest.get("chunks", {}).get("items", [])

        for chunk in chunks:
            for analysis_type in request.analysis_types:
                task_id = str(uuid.uuid4())
                db.create_task(
                    task_id=task_id,
                    video_id=video_id,
                    task_type=f"analysis_{analysis_type}",
                    input_data={
                        "chunk": chunk,
                        "analysis_type": analysis_type,
                    }
                )
                task_ids.append(task_id)

        return AnalysisJobResponse(
            video_id=video_id,
            task_ids=task_ids,
            status="analyzing",
            message=f"Created {len(task_ids)} analysis tasks"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}"
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
async def delete_video(video_id: str):
    """Delete a video and all associated data."""
    try:
        db = get_db()
        storage = get_storage()

        # Get video to find GCS paths
        video = db.get_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}"
            )

        # Delete from GCS (original)
        if video.get("gcs_path"):
            storage.delete_file(video["gcs_path"])

        # Delete manifest and processed files
        manifest = db.get_manifest(video_id)
        if manifest:
            # Delete compressed video
            if manifest.get("compressed", {}).get("gcs_path"):
                storage.delete_file(manifest["compressed"]["gcs_path"])

            # Delete chunks
            for chunk in manifest.get("chunks", {}).get("items", []):
                if chunk.get("gcs_path"):
                    storage.delete_file(chunk["gcs_path"])

            # Delete audio
            if manifest.get("audio", {}).get("gcs_path"):
                storage.delete_file(manifest["audio"]["gcs_path"])

        # Delete from Firestore
        db.videos.document(video_id).delete()
        db.manifests.document(video_id).delete()

        # Delete all tasks for this video
        tasks = db.list_tasks_for_video(video_id)
        for task in tasks:
            db.tasks.document(task["task_id"]).delete()

        # Delete all results for this video
        results = db.get_results_for_video(video_id)
        for result in results:
            if result.get("result_id"):
                db.results.document(result["result_id"]).delete()

        logger.info(f"Deleted video {video_id} and all associated data")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video: {str(e)}"
        )
