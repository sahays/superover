"""Scene job CRUD handlers."""

import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from api.models.schemas import (
    ProcessVideoRequest,
    ProcessingJobResponse,
    SceneJobResponse,
    ResultResponse,
)
from api.middleware.rate_limit import rate_limit
from libs.database import get_db, SceneJobStatus

logger = logging.getLogger(__name__)


def register_job_routes(router: APIRouter) -> None:
    """Register job-related routes on the given router."""

    @router.get("/jobs/{job_id}/results", response_model=List[ResultResponse])
    async def get_results_for_job(job_id: str, result_type: str = None):
        """Get analysis results for a specific scene job."""
        try:
            db = get_db()
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

            query = db.scene_results.where("scene_job_id", "==", job_id)
            for doc in query.stream():
                doc.reference.delete()

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

    # IMPORTANT: Static path routes (/jobs, /jobs/{job_id}) MUST come before
    # parameterized routes (/{video_id}) — otherwise FastAPI matches "jobs" as a video_id.

    @router.get("/jobs", response_model=List[SceneJobResponse])
    async def list_scene_jobs(limit: int = 50, status_filter: SceneJobStatus = None):
        """List all scene jobs."""
        try:
            db = get_db()
            if status_filter:
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

    @router.post(
        "/{video_id}/process",
        response_model=ProcessingJobResponse,
        dependencies=[Depends(rate_limit("scene_analysis"))],
    )
    async def process_video(video_id: str, request: Request, body: ProcessVideoRequest):
        """Start scene processing with user-selected prompt."""
        try:
            db = get_db()

            logger.info("=== process_video API called ===")
            logger.info(f"video_id: {video_id}")
            logger.info(
                f"body.chunk_duration: {body.chunk_duration} (type: {type(body.chunk_duration).__name__})"
            )
            logger.info(f"body.chunk: {body.chunk}")
            logger.info(f"body.compressed_video_path: {body.compressed_video_path}")
            logger.info(f"body.prompt_id: {body.prompt_id}")

            video = db.get_video(video_id)
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video not found: {video_id}",
                )

            prompt = db.get_prompt(body.prompt_id)
            if not prompt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prompt not found: {body.prompt_id}. Please select a valid prompt.",
                )

            prompt_category = prompt.get("type", "custom")
            category_schema_doc = db.get_category_schema(prompt_category)
            response_schema = category_schema_doc.get("response_schema") if category_schema_doc else None

            job_id = str(uuid.uuid4())

            config = {
                "compressed_video_path": body.compressed_video_path,
                "chunk_duration": body.chunk_duration,
                "chunk": body.chunk,
            }

            if body.context_items:
                config["context_items"] = [item.dict() for item in body.context_items]
                logger.info(f"Added {len(body.context_items)} context items to job config")

            logger.info(f"Creating job with config: {config}")

            db.create_scene_job(
                job_id=job_id,
                video_id=video_id,
                config=config,
                prompt_id=body.prompt_id,
                prompt_text=prompt["prompt_text"],
                prompt_type=prompt.get("type", "custom"),
                prompt_name=prompt.get("name"),
                response_schema=response_schema,
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
