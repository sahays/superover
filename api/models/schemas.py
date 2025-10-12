"""Pydantic models for API requests and responses."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


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


class SceneAnalysisRequest(BaseModel):
    """Request to start scene analysis."""
    scene_types: List[str] = Field(
        default=["scene", "objects", "transcription", "moderation"],
        description="Types of scene analysis to perform"
    )


# Backward compatibility alias
AnalyzeVideoRequest = SceneAnalysisRequest


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
    source_type: Optional[str] = 'video'  # 'video' or 'audio', default for backward compatibility
    content_type: Optional[str] = None
    status: Optional[str] = None  # Optional - status lives in jobs now
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


class ProcessingJobResponse(BaseModel):
    """Response for initiated processing job."""
    video_id: str
    status: str
    message: str


class SceneAnalysisJobResponse(BaseModel):
    """Response for initiated scene analysis job."""
    video_id: str
    task_ids: List[str]
    status: str
    message: str


# Backward compatibility alias
AnalysisJobResponse = SceneAnalysisJobResponse


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


# === Media Processing Models ===

class MediaProcessingConfigRequest(BaseModel):
    """Configuration for media processing."""
    compress: bool = Field(True, description="Whether to compress the video")
    compress_resolution: str = Field("480p", description="Target resolution (360p, 480p, 720p, 1080p)")
    extract_audio: bool = Field(True, description="Whether to extract audio")
    audio_format: str = Field("mp3", description="Audio format (mp3, aac, wav)")
    audio_bitrate: str = Field("128k", description="Audio bitrate (128k, 192k, 256k)")
    crf: int = Field(23, description="Constant Rate Factor for video compression (0-51)")
    preset: str = Field("medium", description="Encoding preset (ultrafast, fast, medium, slow, veryslow)")


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
    status: str  # pending, processing, completed, failed
    config: MediaProcessingConfigRequest
    results: Optional[MediaJobResultsResponse] = None
    progress: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None


class MediaPresetResponse(BaseModel):
    """Available media processing presets."""
    resolutions: List[str] = ["360p", "480p", "720p", "1080p", "1440p", "2160p"]
    audio_formats: List[str] = ["mp3", "aac", "wav"]
    audio_bitrates: List[str] = ["128k", "192k", "256k", "320k"]
    presets: List[str] = ["ultrafast", "fast", "medium", "slow", "veryslow"]
    crf_range: Dict[str, int] = {"min": 0, "max": 51, "default": 23}


# === Scene Processing Models ===

class SceneProcessingConfigRequest(BaseModel):
    """Configuration for scene processing."""
    compressed_video_path: Optional[str] = Field(None, description="GCS path to compressed video from media workflow")
    chunk_duration: int = Field(30, description="Chunk duration in seconds (0 = no chunking)")
    chunk: bool = Field(True, description="Whether to chunk the video")

class SceneJobResultsResponse(BaseModel):
    """Results of scene processing job."""
    manifest_created: bool = False
    chunks_analyzed: int = 0
    step: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None

class SceneJobResponse(BaseModel):
    """Scene processing job response."""
    job_id: str
    video_id: str
    status: str  # pending, processing, completed, failed
    config: Dict[str, Any]
    prompt_text: str
    prompt_type: Optional[str] = "custom"
    prompt_name: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None


# === Prompt Management Models ===

PROMPT_TYPES = [
    'scene_analysis',
    'object_identification',
    'subtitling',
    'character_identification',
    'key_moments',
    'action_recognition',
    'sentiment_analysis',
    'brand_detection',
    'custom'
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
    jobs_count: Optional[int] = 0  # Number of jobs using this prompt

class CreatePromptRequest(BaseModel):
    """Request model for creating a new prompt."""
    name: str = Field(..., min_length=3, max_length=100, description="User-friendly name for the prompt")
    type: str = Field(..., description="Type of the prompt")
    prompt_text: str = Field(..., min_length=10, max_length=50000, description="The full text of the prompt")
    supports_context: bool = Field(False, description="Whether this prompt supports additional context files")
    context_description: Optional[str] = Field(None, description="Description of what context is expected")
    required_context_types: Optional[List[str]] = Field(None, description="List of required context types (text, image, video, audio)")
    max_context_items: int = Field(5, description="Maximum number of context items allowed")

    @validator('type')
    def validate_type(cls, v):
        if v not in PROMPT_TYPES:
            raise ValueError(f'Type must be one of: {", ".join(PROMPT_TYPES)}')
        return v

class UpdatePromptRequest(BaseModel):
    """Request model for updating a prompt."""
    name: Optional[str] = Field(None, min_length=3, max_length=100, description="User-friendly name for the prompt")
    type: Optional[str] = Field(None, description="Type of the prompt")
    prompt_text: Optional[str] = Field(None, min_length=10, max_length=50000, description="The full text of the prompt")
    supports_context: Optional[bool] = Field(None, description="Whether this prompt supports additional context files")
    context_description: Optional[str] = Field(None, description="Description of what context is expected")
    required_context_types: Optional[List[str]] = Field(None, description="List of required context types")
    max_context_items: Optional[int] = Field(None, description="Maximum number of context items allowed")

    @validator('type')
    def validate_type(cls, v):
        if v is not None and v not in PROMPT_TYPES:
            raise ValueError(f'Type must be one of: {", ".join(PROMPT_TYPES)}')
        return v
