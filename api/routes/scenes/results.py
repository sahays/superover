"""Scene result and manifest handlers."""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import ManifestResponse, ResultResponse
from libs.database import get_db

logger = logging.getLogger(__name__)


def register_result_routes(router: APIRouter) -> None:
    """Register result-related routes on the given router."""

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
