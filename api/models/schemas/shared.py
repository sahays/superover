"""Shared request/response models (uploads, videos, health)."""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# === Request Models ===

ALLOWED_MEDIA_TYPES = ("video/", "audio/")


class SignedUrlRequest(BaseModel):
    """Request for generating a signed upload URL."""

    filename: str = Field(..., description="Name of the file to upload")
    content_type: str = Field(..., description="MIME type of the file (must be audio/* or video/*)")

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if not v.startswith(ALLOWED_MEDIA_TYPES):
            raise ValueError(f"Only audio and video files are allowed. Got: {v}")
        return v


class CreateVideoRequest(BaseModel):
    """Request to create a video record after upload."""

    filename: str
    gcs_path: str
    content_type: str
    size_bytes: int
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if not v.startswith(ALLOWED_MEDIA_TYPES):
            raise ValueError(f"Only audio and video files are allowed. Got: {v}")
        return v


class ContextItemRequest(BaseModel):
    """Context item for scene analysis."""

    context_id: str = Field(..., description="Unique ID for the context item")
    type: str = Field(..., description="Type of context (text, image, video, audio)")
    gcs_path: str = Field(..., description="GCS path to the context file")
    filename: str = Field(..., description="Original filename")
    description: Optional[str] = Field(None, description="Optional description of the context")
    size_bytes: int = Field(..., description="File size in bytes")


class ProcessVideoRequest(BaseModel):
    """Request to start scene processing."""

    prompt_id: str = Field(..., description="ID of the prompt to use for scene analysis (required)")
    compressed_video_path: Optional[str] = Field(None, description="GCS path to compressed video from media workflow")
    chunk_duration: int = Field(30, description="Chunk duration in seconds (0 = no chunking)")
    compress: bool = Field(False, description="Whether to compress (deprecated - use media workflow)")
    chunk: bool = Field(True, description="Whether to chunk the video")
    extract_audio: bool = Field(False, description="Whether to extract audio (deprecated - use media workflow)")
    context_items: Optional[List[ContextItemRequest]] = Field(None, description="Optional context files for analysis")


# === Response Models ===


class SignedUrlResponse(BaseModel):
    """Response with signed upload URL."""

    signed_url: str
    gcs_path: str
    expires_in_minutes: int = 15


class VideoResponse(BaseModel):
    """Video information response."""

    video_id: str
    filename: str
    gcs_path: str
    source_type: Optional[str] = "video"
    content_type: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ManifestResponse(BaseModel):
    """Processing manifest response."""

    video_id: str
    version: str
    original: Dict[str, Any]
    compressed: Optional[Dict[str, Any]] = None
    chunks: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    audio: Optional[Dict[str, Any]] = None
    processing: Optional[Dict[str, Any]] = None


class ProcessingJobResponse(BaseModel):
    """Response for initiated processing job."""

    video_id: str
    status: str
    message: str


class ResultResponse(BaseModel):
    """Analysis result response."""

    result_id: str
    video_id: str
    result_type: str
    result_data: Dict[str, Any]
    gcs_path: Optional[str] = None
    created_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    environment: str
    timestamp: datetime
