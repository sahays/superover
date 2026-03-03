"""Media processing schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class MediaProcessingConfigRequest(BaseModel):
    """Configuration for media processing."""

    compress: bool = Field(True, description="Whether to compress the video")
    compress_resolution: str = Field("480p", description="Target resolution (360p, 480p, 720p, 1080p)")
    extract_audio: bool = Field(True, description="Whether to extract audio")
    audio_format: str = Field("mp3", description="Audio format (mp3, aac, wav)")
    audio_bitrate: str = Field("128k", description="Audio bitrate (128k, 192k, 256k)")
    crf: int = Field(23, description="Constant Rate Factor for video compression (0-51)")


class CreateMediaJobRequest(BaseModel):
    """Request to create a media processing job."""

    video_id: str = Field(..., description="ID of the video to process")
    config: MediaProcessingConfigRequest = Field(default_factory=MediaProcessingConfigRequest)


class MediaJobResultsResponse(BaseModel):
    """Results of media processing job."""

    metadata: Dict[str, Any]
    compressed_video_path: Optional[str] = None
    audio_path: Optional[str] = None
    original_size_bytes: int = 0
    compressed_size_bytes: int = 0
    compression_ratio: float = 0.0
    audio_size_bytes: int = 0


class MediaJobResponse(BaseModel):
    """Media processing job response."""

    job_id: str
    video_id: str
    status: str
    config: MediaProcessingConfigRequest
    results: Optional[MediaJobResultsResponse] = None
    progress: Optional[Dict[str, Any]] = None
    transcoder_job_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None


class MediaPresetResponse(BaseModel):
    """Available media processing presets."""

    resolutions: List[str] = ["360p", "480p", "720p", "1080p", "1440p", "2160p"]
    audio_formats: List[str] = ["mp3", "aac", "wav"]
    audio_bitrates: List[str] = ["128k", "192k", "256k", "320k"]
    crf_range: Dict[str, int] = {"min": 0, "max": 51, "default": 23}
