"""Category schema models."""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class CategorySchemaResponse(BaseModel):
    """Response model for a category's JSON response schema."""

    category: str
    response_schema: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None


class SetCategorySchemaRequest(BaseModel):
    """Request model for setting a category's JSON response schema."""

    response_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for structured Gemini responses. null = free text."
    )
