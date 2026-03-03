"""Image adaptation schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ImageProcessingConfigRequest(BaseModel):
    """Configuration for image adaptation."""

    aspect_ratios: List[str] = Field(..., description="List of target aspect ratios (e.g. ['16:9', '9:16'])")
    resolution: str = Field("HD", description="Target resolution (HD, 4K, Original)")


class CreateImageJobRequest(BaseModel):
    """Request to create an image adaptation job."""

    video_id: str = Field(..., description="ID of the image asset to process")
    prompt_id: str = Field(..., description="ID of the prompt to use")
    config: ImageProcessingConfigRequest


class ImageJobResponse(BaseModel):
    """Image adaptation job response."""

    job_id: str
    video_id: str
    status: str
    config: ImageProcessingConfigRequest
    prompt_text: str
    prompt_type: str
    prompt_name: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    stop_reason: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
