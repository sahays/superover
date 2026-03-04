"""Branding settings schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BrandingResponse(BaseModel):
    """Branding settings response."""

    app_title: str
    subtitle: str
    logo_url: str
    updated_at: Optional[datetime] = None


class UpdateBrandingRequest(BaseModel):
    """Update branding settings request. At least one field must be provided."""

    app_title: Optional[str] = Field(None, min_length=1, max_length=100)
    subtitle: Optional[str] = Field(None, max_length=200)
    logo_url: Optional[str] = Field(None, max_length=2000)
