"""Prompt management schemas."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


PROMPT_TYPES = [
    "scene_analysis",
    "object_identification",
    "subtitling",
    "key_moments",
    "cliffhanger_analysis",
    "image_adaptation",
    "custom",
]


class PromptResponse(BaseModel):
    """Response model for a prompt."""

    prompt_id: str
    name: str
    type: str
    prompt_text: str
    supports_context: bool = False
    context_description: Optional[str] = None
    required_context_types: Optional[List[str]] = None
    max_context_items: Optional[int] = 5
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    jobs_count: Optional[int] = 0


class CreatePromptRequest(BaseModel):
    """Request model for creating a new prompt."""

    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="User-friendly name for the prompt",
    )
    type: str = Field(..., description="Type of the prompt")
    prompt_text: str = Field(..., min_length=10, max_length=50000, description="The full text of the prompt")
    supports_context: bool = Field(False, description="Whether this prompt supports additional context files")
    context_description: Optional[str] = Field(None, description="Description of what context is expected")
    required_context_types: Optional[List[str]] = Field(
        None, description="List of required context types (text, image, video, audio)"
    )
    max_context_items: int = Field(5, description="Maximum number of context items allowed")

    @validator("type")
    def validate_type(cls, v):
        if v not in PROMPT_TYPES:
            raise ValueError(f"Type must be one of: {', '.join(PROMPT_TYPES)}")
        return v


class UpdatePromptRequest(BaseModel):
    """Request model for updating a prompt."""

    name: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="User-friendly name for the prompt",
    )
    type: Optional[str] = Field(None, description="Type of the prompt")
    prompt_text: Optional[str] = Field(None, min_length=10, max_length=50000, description="The full text of the prompt")
    supports_context: Optional[bool] = Field(None, description="Whether this prompt supports additional context files")
    context_description: Optional[str] = Field(None, description="Description of what context is expected")
    required_context_types: Optional[List[str]] = Field(None, description="List of required context types")
    max_context_items: Optional[int] = Field(None, description="Maximum number of context items allowed")

    @validator("type")
    def validate_type(cls, v):
        if v is not None and v not in PROMPT_TYPES:
            raise ValueError(f"Type must be one of: {', '.join(PROMPT_TYPES)}")
        return v
