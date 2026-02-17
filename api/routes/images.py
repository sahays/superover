"""
Image Adaptation Routes
Endpoints for managing image adaptation jobs and results.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict
import uuid

from api.models.schemas import CreateImageJobRequest, ImageJobResponse
from libs.database import get_db

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/jobs", response_model=ImageJobResponse, status_code=201)
async def create_image_job(request: CreateImageJobRequest):
    """Create a new image adaptation job."""
    db = get_db()

    # Verify asset exists
    asset = db.get_video(request.video_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Verify prompt exists
    prompt = db.get_prompt(request.prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    job_id = str(uuid.uuid4())

    job = db.create_image_job(
        job_id=job_id,
        video_id=request.video_id,
        config=request.config.dict(),
        prompt_id=request.prompt_id,
        prompt_text=prompt["prompt_text"],
        prompt_type=prompt["type"],
        prompt_name=prompt.get("name"),
    )

    return job


@router.get("/jobs/{job_id}", response_model=ImageJobResponse)
async def get_image_job(job_id: str):
    """Get image job details."""
    db = get_db()
    job = db.get_image_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/asset/{asset_id}", response_model=List[ImageJobResponse])
async def list_image_jobs_for_asset(asset_id: str):
    """List all image jobs for a specific asset."""
    db = get_db()
    return db.list_image_jobs_for_video(asset_id)


@router.get("/results/{result_id}/download")
async def get_image_download_url(result_id: str):
    """Generate a signed URL for an image result."""
    # TODO: implement signed URL generation from GCS path
    pass


@router.post("/signed-url")
async def get_signed_url(gcs_path: str):
    """Generate a signed URL for any GCS path (Internal use)."""
    from libs.storage import get_storage

    storage = get_storage()
    url = storage.generate_signed_download_url(gcs_path)
    return {"url": url}


@router.get("/jobs/{job_id}/results", response_model=List[Dict])
async def get_image_results(job_id: str):
    """Get results for an image job."""
    db = get_db()
    return db.get_results_for_image_job(job_id)
