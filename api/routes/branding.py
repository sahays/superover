"""Branding settings API routes."""

import logging
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import BrandingResponse, UpdateBrandingRequest
from libs.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("", response_model=BrandingResponse)
async def get_branding():
    """Get current branding settings."""
    db = get_db()
    return db.get_branding()


@router.put("", response_model=BrandingResponse)
async def update_branding(request: UpdateBrandingRequest):
    """Update branding settings."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )
    db = get_db()
    return db.update_branding(updates)
