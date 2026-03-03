"""Signed URL upload handlers for scenes."""

import uuid
import logging
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import SignedUrlRequest, SignedUrlResponse
from libs.storage import get_storage

logger = logging.getLogger(__name__)


def register_upload_routes(router: APIRouter) -> None:
    """Register upload-related routes on the given router."""

    @router.post("/signed-url", response_model=SignedUrlResponse)
    async def get_signed_upload_url(request: SignedUrlRequest):
        """Generate a signed URL for direct video upload to GCS."""
        try:
            storage = get_storage()
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
        """Generate a signed URL for direct context file upload to GCS."""
        try:
            storage = get_storage()
            file_ext = request.filename.split(".")[-1] if "." in request.filename else "txt"
            unique_filename = f"context/{uuid.uuid4()}.{file_ext}"

            signed_url, gcs_path = storage.generate_signed_upload_url(
                filename=unique_filename,
                content_type=request.content_type,
                bucket_type="processed",
            )

            return SignedUrlResponse(signed_url=signed_url, gcs_path=gcs_path, expires_in_minutes=15)

        except Exception as e:
            logger.error(f"Failed to generate context signed URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate context signed URL: {str(e)}",
            )
