"""Scene processing schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class SceneAnalysisRequest(BaseModel):
    """Request to start scene analysis."""

    scene_types: List[str] = Field(
        default=["scene", "objects", "transcription", "moderation"],
        description="Types of scene analysis to perform",
    )


# Backward compatibility alias
AnalyzeVideoRequest = SceneAnalysisRequest


class SceneAnalysisJobResponse(BaseModel):
    """Response for initiated scene analysis job."""

    video_id: str
    task_ids: List[str]
    status: str
    message: str


# Backward compatibility alias
AnalysisJobResponse = SceneAnalysisJobResponse


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
    token_usage: Optional[Dict[str, Any]] = None


class SceneJobResponse(BaseModel):
    """Scene processing job response."""

    job_id: str
    video_id: str
    status: str
    config: Dict[str, Any]
    prompt_text: str
    prompt_type: Optional[str] = "custom"
    prompt_name: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
