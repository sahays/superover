"""Auth schemas for invite code system."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ValidateCodeRequest(BaseModel):
    code: str = Field(..., description="Invite code to validate")


class ValidateCodeResponse(BaseModel):
    valid: bool
    is_master: bool
    # Admin = stored invite code with is_admin=True. Grants master-level access
    # everywhere EXCEPT creating new invite codes. Distinct from is_master,
    # which is reserved for the env-var holder.
    is_admin: bool = False
    # Studio slug scoping this code's content visibility ("" = sees everything,
    # used by master/operator). Drives per-tenant search isolation.
    owner: str = ""


class InviteCodeResponse(BaseModel):
    id: str
    code: str
    label: str = ""
    is_active: bool = True
    is_admin: bool = False
    owner: str = ""
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CreateInviteCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="The invite code string")
    label: str = Field("", max_length=200, description="Human-readable label")
    is_admin: bool = Field(False, description="Grant master-level access except code creation")
    owner: str = Field("", max_length=100, description="Studio slug scoping content visibility")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class UpdateInviteCodeRequest(BaseModel):
    label: Optional[str] = Field(None, max_length=200, description="Human-readable label")
    owner: Optional[str] = Field(None, max_length=100, description="Studio slug scoping content visibility")
