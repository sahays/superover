"""Pydantic models for API requests and responses."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from libs.database import VideoStatus, TaskStatus


# === Request Models ===

class SignedUrlRequest(BaseModel):
    """Request for generating a signed upload URL."""
    filename: str = Field(..., description="Name of the file to upload")
    content_type: str = Field(..., description="MIME type of the file")


class CreateVideoRequest(BaseModel):
    """Request to create a video record after upload."""
    filename: str
    gcs_path: str
    content_type: str
    size_bytes: int
    metadata: Optional[Dict[str, Any]] = None


class ProcessVideoRequest(BaseModel):
    """Request to start video processing."""
    compress: bool = Field(True, description="Whether to compress the video")
    chunk: bool = Field(True, description="Whether to chunk the video")
    extract_audio: bool = Field(True, description="Whether to extract audio")


class AnalyzeVideoRequest(BaseModel):
    """Request to start video analysis."""
    analysis_types: List[str] = Field(
        default=["scene", "objects", "transcription", "moderation"],
        description="Types of analysis to perform"
    )


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
    status: VideoStatus
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
    chunks: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    processing: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Analysis task response."""
    task_id: str
    video_id: str
    task_type: str
    status: TaskStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ProcessingJobResponse(BaseModel):
    """Response for initiated processing job."""
    video_id: str
    status: str
    message: str


class AnalysisJobResponse(BaseModel):
    """Response for initiated analysis job."""
    video_id: str
    task_ids: List[str]
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
