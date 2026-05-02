"""Avatar CRUD + live-config + live-token — drives the Gemini Live persona library.

The /live WebSocket relay lives in `avatars_live.py`; both routers mount under
`/api/avatars`.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from api.models.schemas.avatars import (
    Avatar,
    AvatarResponse,
    CreateAvatarRequest,
    LiveConfigResponse,
    LiveTokenResponse,
    UpdateAvatarRequest,
)
from libs.avatar_service import build_system_instruction
from libs.avatar_token import mint_live_token
from libs.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/avatars", tags=["avatars"])


def _avatar_from_record(record: dict) -> Avatar:
    """Drop unknown keys (e.g. legacy `archived`) before constructing the model."""
    return Avatar(**{k: v for k, v in record.items() if k in Avatar.model_fields})


def _serialize(record: dict) -> AvatarResponse:
    avatar = _avatar_from_record(record)
    return AvatarResponse(
        id=avatar.id,
        name=avatar.name,
        style=avatar.style,
        persona_prompt=avatar.persona_prompt,
        behavior_instructions=avatar.behavior_instructions,
        voice=avatar.voice,
        preset_name=avatar.preset_name,
        language=avatar.language,
        default_greeting=avatar.default_greeting,
        enable_grounding=avatar.enable_grounding,
        created_at=record.get("created_at"),
    )


def _get_or_404(avatar_id: str) -> dict:
    record = get_db().get_avatar(avatar_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    return record


@router.get("", response_model=List[AvatarResponse])
async def list_avatars():
    return [_serialize(r) for r in get_db().list_avatars()]


@router.get("/{avatar_id}", response_model=AvatarResponse)
async def get_avatar(avatar_id: str):
    return _serialize(_get_or_404(avatar_id))


@router.post("", response_model=AvatarResponse, status_code=status.HTTP_201_CREATED)
async def create_avatar(body: CreateAvatarRequest):
    avatar = Avatar(
        name=body.name.strip() or "Untitled",
        style=body.style,
        persona_prompt=body.persona_prompt.strip(),
        behavior_instructions=body.behavior_instructions.strip(),
        voice=body.voice,
        preset_name=body.preset_name,
        language=body.language or "en-US",
        default_greeting=(body.default_greeting or "").strip(),
        enable_grounding=body.enable_grounding,
    )
    record = get_db().create_avatar(avatar.model_dump(mode="json"))
    return _serialize(record)


@router.patch("/{avatar_id}", response_model=AvatarResponse)
async def update_avatar(avatar_id: str, body: UpdateAvatarRequest):
    _get_or_404(avatar_id)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    # Strip strings to keep the persona prompt and greeting tidy in storage.
    for key in ("name", "persona_prompt", "behavior_instructions", "default_greeting"):
        if key in updates and isinstance(updates[key], str):
            updates[key] = updates[key].strip()
    record = get_db().update_avatar(avatar_id, updates)
    return _serialize(record)  # type: ignore[arg-type]


@router.delete("/{avatar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(avatar_id: str):
    _get_or_404(avatar_id)
    get_db().delete_avatar(avatar_id)


@router.get("/{avatar_id}/live-config", response_model=LiveConfigResponse)
async def live_config(avatar_id: str):
    """Non-secret config for the live UI: voice, system instruction, preset."""
    avatar = _avatar_from_record(_get_or_404(avatar_id))
    return LiveConfigResponse(
        voice=avatar.voice.value,
        language=avatar.language or "en-US",
        system_instruction=build_system_instruction(avatar),
        preset_name=avatar.preset_name,
        default_greeting=avatar.default_greeting,
        enable_grounding=avatar.enable_grounding,
    )


@router.post("/{avatar_id}/live-token", response_model=LiveTokenResponse)
async def live_token(avatar_id: str):
    """Mint a single-use signed token for the /live WebSocket upgrade.

    HTTP middleware doesn't run on WS upgrades — instead of carrying the
    invite code on the WS query string (where it would land in access logs),
    the frontend hits this endpoint over authenticated HTTP, gets a short
    HMAC token bound to this avatar id, and presents it on the upgrade.
    """
    _get_or_404(avatar_id)
    token, expires_at = mint_live_token(avatar_id)
    return LiveTokenResponse(token=token, expires_at=expires_at)
