"""Dubbing API routes for multilingual voice translation, track muxing, and playback."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from api.models.schemas.dubbing import (
    CreateDubbingJobRequest,
    DubbingJobResponse,
    DubbingLanguage,
    DubbingPlaybackResponse,
    DubbingTrackInfo,
)
from libs.database import get_db
from libs.db.enums import DubbingJobStatus
from libs.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dubbing", tags=["dubbing"])


def _serialize_dubbing_job(record: Dict[str, Any]) -> DubbingJobResponse:
    """Format raw Firestore document into typed DubbingJobResponse model."""
    raw_tracks = record.get("tracks", {})
    typed_tracks: Dict[str, DubbingTrackInfo] = {}

    for lang, track in raw_tracks.items():
        try:
            typed_tracks[lang] = DubbingTrackInfo(**track)
        except Exception as e:
            logger.warning(f"[DubbingRoutes] Could not serialize track {lang}: {e}")

    return DubbingJobResponse(
        job_id=record["job_id"],
        video_id=record["video_id"],
        status=DubbingJobStatus(record["status"]),
        config=record.get("config", {}),
        tracks=typed_tracks,
        source_audio_path=record.get("source_audio_path"),
        source_dialog_path=record.get("source_dialog_path"),
        error_message=record.get("error_message"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


@router.post("/jobs", response_model=DubbingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_dubbing_job(body: CreateDubbingJobRequest):
    """Create and submit a new multilingual video dubbing job."""
    db = get_db()
    video = db.get_video(body.video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {body.video_id}",
        )

    if not body.config.target_languages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one target language must be selected for dubbing.",
        )

    job_id = str(uuid.uuid4())
    logger.info(
        f"[DubbingRoutes] Creating dubbing job {job_id} for video {body.video_id} "
        f"with languages {[lang.value for lang in body.config.target_languages]}"
    )

    record = db.create_dubbing_job(
        job_id=job_id,
        video_id=body.video_id,
        config=body.config.model_dump(mode="json"),
    )
    return _serialize_dubbing_job(record)


@router.get("/jobs", response_model=List[DubbingJobResponse])
async def list_dubbing_jobs(
    limit: int = 50,
    video_id: Optional[str] = None,
    status_filter: Optional[DubbingJobStatus] = None,
):
    """List dubbing jobs with optional filtering by video_id and status."""
    db = get_db()
    if video_id:
        records = db.list_dubbing_jobs_for_video(video_id)
    else:
        records = db.list_dubbing_jobs(limit=limit, status=status_filter)

    return [_serialize_dubbing_job(r) for r in records]


@router.get("/jobs/{job_id}", response_model=DubbingJobResponse)
async def get_dubbing_job(job_id: str):
    """Retrieve full dubbing job record and language tracks."""
    db = get_db()
    record = db.get_dubbing_job(job_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dubbing job not found: {job_id}",
        )
    return _serialize_dubbing_job(record)


@router.get("/jobs/{job_id}/playback/{language}", response_model=DubbingPlaybackResponse)
async def get_dubbing_playback_url(
    job_id: str,
    language: DubbingLanguage,
    media_type: str = "video",
):
    """Generate time-limited signed URL for streaming or downloading dubbed output.

    Args:
        job_id: Dubbing job identifier.
        language: Target language code (e.g. hi-IN, es-ES, pt-BR, de-DE, en-US).
        media_type: 'video' for muxed video rendition, or 'audio' for isolated speech stream.
    """
    db = get_db()
    record = db.get_dubbing_job(job_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dubbing job not found: {job_id}",
        )

    tracks = record.get("tracks", {})
    lang_key = language.value if hasattr(language, "value") else str(language)
    track = tracks.get(lang_key)

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No dubbed track available for language '{lang_key}' on job {job_id}.",
        )

    storage = get_storage()
    if media_type == "audio":
        gcs_path = track.get("audio_gcs_path")
        content_type = "audio/wav"
    else:
        gcs_path = track.get("video_gcs_path") or track.get("audio_gcs_path")
        content_type = "video/mp4" if gcs_path and gcs_path.endswith(".mp4") else "audio/wav"

    if not gcs_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media file path not found for track {lang_key}.",
        )

    signed_url = storage.generate_signed_download_url(
        gcs_path=gcs_path,
        expiration_minutes=60,
        response_content_type=content_type,
    )

    return DubbingPlaybackResponse(
        signed_url=signed_url,
        content_type=content_type,
        language=lang_key,
        media_type="video" if content_type.startswith("video/") else "audio",
        expires_in_minutes=60,
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dubbing_job(job_id: str):
    """Delete a dubbing job record and clean up associated GCS artifacts."""
    db = get_db()
    record = db.get_dubbing_job(job_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dubbing job not found: {job_id}",
        )

    storage = get_storage()
    # Clean up generated audio and video files
    for lang, track in record.get("tracks", {}).items():
        if track.get("audio_gcs_path"):
            try:
                storage.delete_file(track["audio_gcs_path"])
            except Exception as e:
                logger.warning(f"[DubbingRoutes] Could not delete audio {track['audio_gcs_path']}: {e}")
        if track.get("video_gcs_path"):
            try:
                storage.delete_file(track["video_gcs_path"])
            except Exception as e:
                logger.warning(f"[DubbingRoutes] Could not delete video {track['video_gcs_path']}: {e}")

    db.delete_dubbing_job(job_id)
    logger.info(f"[DubbingRoutes] Deleted dubbing job {job_id} and storage files")
