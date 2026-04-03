"""Auth schemas for invite code system."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ValidateCodeRequest(BaseModel):
    code: str = Field(..., description="Invite code to validate")


class ValidateCodeResponse(BaseModel):
    valid: bool
    is_master: bool


class InviteCodeResponse(BaseModel):
    id: str
    code: str
    label: str = ""
    is_active: bool = True
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CreateInviteCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="The invite code string")
    label: str = Field("", max_length=200, description="Human-readable label")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class UpdateInviteCodeRequest(BaseModel):
    label: Optional[str] = Field(None, max_length=200, description="Human-readable label")
