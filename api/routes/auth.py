"""Auth routes for invite code validation and management."""

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Request, status

from config import settings
from libs.database import get_db
from api.models.schemas.auth import (
    ValidateCodeRequest,
    ValidateCodeResponse,
    InviteCodeResponse,
    CreateInviteCodeRequest,
    UpdateInviteCodeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_master(code: str) -> bool:
    master = settings.master_invite_code
    return bool(master and code == master)


def validate_code(code: str) -> dict:
    """Validate an invite code. Returns {valid, is_master}."""
    if _is_master(code):
        return {"valid": True, "is_master": True}

    db = get_db()
    invite = db.get_invite_code_by_value(code)
    if not invite:
        return {"valid": False, "is_master": False}

    if not invite.get("is_active", True):
        return {"valid": False, "is_master": False}

    expires_at = invite.get("expires_at")
    if expires_at and expires_at < datetime.now(timezone.utc):
        return {"valid": False, "is_master": False}

    return {"valid": True, "is_master": False}


def _require_master(request: Request) -> None:
    if not getattr(request.state, "is_master", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master access required")


# --- Public endpoint ---


@router.post("/validate", response_model=ValidateCodeResponse)
async def validate_invite_code(body: ValidateCodeRequest):
    """Validate an invite code (public, no auth required)."""
    result = validate_code(body.code)
    return ValidateCodeResponse(**result)


# --- Master-only endpoints ---


@router.get("/codes", response_model=List[InviteCodeResponse])
async def list_codes(request: Request):
    """List all invite codes (master only)."""
    _require_master(request)
    db = get_db()
    codes = db.get_invite_codes()
    return [InviteCodeResponse(**c) for c in codes]


@router.post("/codes", response_model=InviteCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_code(request: Request, body: CreateInviteCodeRequest):
    """Create a new invite code (master only)."""
    _require_master(request)
    db = get_db()

    existing = db.get_invite_code_by_value(body.code)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code already exists")

    code = db.create_invite_code(
        code=body.code,
        label=body.label,
        expires_at=body.expires_at,
    )
    return InviteCodeResponse(**code)


@router.patch("/codes/{code_id}", response_model=InviteCodeResponse)
async def update_code(request: Request, code_id: str, body: UpdateInviteCodeRequest):
    """Update an invite code (master only)."""
    _require_master(request)
    db = get_db()

    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    result = db.update_invite_code(code_id, updates)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    return InviteCodeResponse(**result)


@router.post("/codes/{code_id}/revoke", response_model=InviteCodeResponse)
async def revoke_code(request: Request, code_id: str):
    """Deactivate an invite code (master only)."""
    _require_master(request)
    db = get_db()
    result = db.update_invite_code(code_id, {"is_active": False})
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    return InviteCodeResponse(**result)


@router.post("/codes/{code_id}/activate", response_model=InviteCodeResponse)
async def activate_code(request: Request, code_id: str):
    """Reactivate an invite code (master only)."""
    _require_master(request)
    db = get_db()
    result = db.update_invite_code(code_id, {"is_active": True})
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    return InviteCodeResponse(**result)


@router.delete("/codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code(request: Request, code_id: str):
    """Delete an invite code (master only)."""
    _require_master(request)
    db = get_db()
    existing = db.get_invite_code(code_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    db.delete_invite_code(code_id)
