"""
Engagement Analysis Routes
Endpoints for uploading BARC data, creating engagement jobs, and reading results.
"""

import json
import logging
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from api.models.schemas import (
    BarcSignedUrlRequest,
    CreateEngagementJobRequest,
    EligibleSourceJob,
    EngagementJobResponse,
    EngagementTimeseriesResponse,
)
from api.models.schemas.shared import SignedUrlResponse
from libs.database import get_db
from libs.db.enums import SceneJobStatus
from libs.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/engagement", tags=["engagement"])


@router.post("/signed-url", response_model=SignedUrlResponse)
async def get_barc_signed_url(body: BarcSignedUrlRequest):
    """Generate a signed URL for direct BARC CSV upload to GCS."""
    try:
        storage = get_storage()
        file_ext = body.filename.split(".")[-1] if "." in body.filename else "csv"
        unique_filename = f"engagement/{uuid.uuid4()}.{file_ext}"

        signed_url, gcs_path = storage.generate_signed_upload_url(
            filename=unique_filename,
            content_type=body.content_type,
            bucket_type="uploads",
        )
        return SignedUrlResponse(signed_url=signed_url, gcs_path=gcs_path, expires_in_minutes=15)
    except Exception as e:
        logger.error(f"Failed to generate engagement signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {e}",
        )


@router.post("/jobs", response_model=EngagementJobResponse, status_code=201)
async def create_engagement_job(request: CreateEngagementJobRequest):
    """Create a new engagement analysis job."""
    db = get_db()

    video = db.get_video(request.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    source_job = db.get_scene_job(request.source_scene_job_id)
    if not source_job:
        raise HTTPException(status_code=404, detail="Source scene job not found")
    if source_job.get("video_id") != request.video_id:
        raise HTTPException(
            status_code=400,
            detail="Source scene job does not belong to the specified video",
        )
    if source_job.get("status") != SceneJobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Source scene job must be in COMPLETED status",
        )

    job_id = str(uuid.uuid4())
    job = db.create_engagement_job(
        job_id=job_id,
        video_id=request.video_id,
        source_scene_job_id=request.source_scene_job_id,
        barc_gcs_path=request.barc_gcs_path,
        config=request.config,
    )
    return job


@router.get("/jobs/{job_id}", response_model=EngagementJobResponse)
async def get_engagement_job(job_id: str):
    """Get engagement job details."""
    db = get_db()
    job = db.get_engagement_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/videos/{video_id}/jobs", response_model=List[EngagementJobResponse])
async def list_engagement_jobs_for_video(video_id: str):
    """List all engagement jobs for a video, newest first."""
    db = get_db()
    return db.list_engagement_jobs_for_video(video_id)


@router.get("/videos/{video_id}/scene-jobs", response_model=List[EligibleSourceJob])
async def list_eligible_source_jobs(video_id: str):
    """List completed scene jobs for a video, eligible as engagement context source."""
    db = get_db()
    jobs = db.list_scene_jobs_for_video(video_id, status=SceneJobStatus.COMPLETED)
    return _to_eligible(jobs)


@router.get("/scene-jobs", response_model=List[EligibleSourceJob])
async def list_all_eligible_source_jobs(limit: int = 100):
    """List all completed scene jobs across the system (newest first).

    Uses a status-only query then sorts in Python — avoids needing a
    composite Firestore index on (status, created_at).
    """
    db = get_db()
    query = db.scene_jobs.where("status", "==", SceneJobStatus.COMPLETED).limit(limit)
    items = [doc.to_dict() for doc in query.stream()]
    items.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    return _to_eligible(items)


def _to_eligible(jobs: list) -> list:
    """Map raw scene jobs to the EligibleSourceJob shape (no prompt_type filter)."""
    return [
        EligibleSourceJob(
            job_id=j["job_id"],
            video_id=j["video_id"],
            prompt_name=j.get("prompt_name"),
            prompt_type=j.get("prompt_type"),
            created_at=j.get("created_at"),
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}/timeseries", response_model=EngagementTimeseriesResponse)
async def get_engagement_timeseries(job_id: str):
    """Fetch the normalized multi-metric BARC timeseries used for charting."""
    data = _load_results_artifact(job_id, "timeseries_gcs_path", "timeseries")

    metrics = data.get("metrics") or {}
    # Back-compat: older jobs stored `points` (primary metric only).
    if not metrics and data.get("points"):
        primary = data.get("score_column") or "score"
        metrics = {primary: data["points"]}

    primary_metric = data.get("primary_metric") or data.get("score_column")
    primary_points = metrics.get(primary_metric, []) if primary_metric else []

    return EngagementTimeseriesResponse(
        points=primary_points,
        metrics=metrics,
        primary_metric=primary_metric,
        time_column=data.get("time_column"),
        score_column=data.get("score_column"),
    )


@router.get("/jobs/{job_id}/entities")
async def get_engagement_entities(job_id: str):
    """Fetch the entity list mined / extracted from the source scene job."""
    return _load_results_artifact(job_id, "entities_gcs_path", "entities")


@router.get("/jobs/{job_id}/cues")
async def get_engagement_cues(job_id: str):
    """Fetch the merged dialog/narration cues — powers the click-a-point drawer."""
    return _load_results_artifact(job_id, "cues_gcs_path", "cues")


@router.get("/jobs/{job_id}/recommendations")
async def get_engagement_recommendations(job_id: str):
    """Fetch grounded 'do more / do less / per-minute' recommendations."""
    return _load_results_artifact(job_id, "recommendations_gcs_path", "recommendations")


def _load_results_artifact(job_id: str, gcs_path_key: str, artifact_label: str):
    """Shared helper: fetch one of the engagement results JSON files from GCS.

    Returns the parsed JSON. Raises 404 if the job or path is missing,
    500 on download/parse failure.
    """
    db = get_db()
    job = db.get_engagement_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results = job.get("results") or {}
    gcs_path = results.get(gcs_path_key)
    if not gcs_path:
        raise HTTPException(status_code=404, detail=f"No {artifact_label} available yet")

    storage = get_storage()
    bucket_name, blob_name = storage._parse_gcs_path(gcs_path)
    blob = storage.client.bucket(bucket_name).blob(blob_name)
    try:
        return json.loads(blob.download_as_bytes())
    except Exception as e:
        logger.error(f"Failed to read {artifact_label} from {gcs_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read {artifact_label}")


@router.delete("/jobs/{job_id}")
async def delete_engagement_job(job_id: str):
    """Delete an engagement job."""
    db = get_db()
    job = db.get_engagement_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete_engagement_job(job_id)
    return {"status": "deleted"}
