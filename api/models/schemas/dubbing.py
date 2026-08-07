"""Dubbing Pydantic schemas."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from libs.db.enums import DubbingJobStatus, DubbingLanguage, DubbingMode
from api.models.schemas.avatars import AvatarVoice


class DubbingConfigRequest(BaseModel):
    """Configuration options for a dubbing job."""

    target_languages: List[DubbingLanguage] = Field(
        default=[DubbingLanguage.HINDI, DubbingLanguage.SPANISH],
        description="Target languages to generate dubbing for (Hindi, English, Portuguese, Spanish, German)",
    )
    voice: AvatarVoice = Field(
        default=AvatarVoice.Kore,
        description="Prebuilt voice persona preset used for synthesizing dubbed audio tracks",
    )
    mode: DubbingMode = Field(
        default=DubbingMode.VOICEOVER,
        description="Audio mix strategy: voiceover (with ducking), replace (clean dialogue), or isolated",
    )
    ducking_db: float = Field(
        default=-18.0,
        description="Volume attenuation in dB for original background dialogue during speech overlay",
    )
    source_language: str = Field(
        default="auto",
        description="Source audio language (auto for auto-detection, or ISO code e.g. en-US)",
    )


class CreateDubbingJobRequest(BaseModel):
    """Request to create a new multilingual dubbing job."""

    video_id: str = Field(..., description="ID of the video asset in the library to dub")
    config: DubbingConfigRequest = Field(default_factory=DubbingConfigRequest)


class TimedDubbingSegment(BaseModel):
    """A discrete timed spoken dialogue line translated and synthesized."""

    speaker: str = Field("Speaker", description="Identified speaker or persona")
    start_seconds: float = Field(..., description="Start timestamp in seconds")
    end_seconds: float = Field(..., description="End timestamp in seconds")
    original_text: str = Field(..., description="Original transcribed speech text")
    translated_text: str = Field(..., description="Context-aware translated speech text")
    confidence: float = Field(1.0, description="Pacing and alignment confidence score")


class DubbingTrackInfo(BaseModel):
    """Metadata and paths for a specific dubbed language track."""

    language: DubbingLanguage = Field(..., description="Language code")
    language_label: str = Field(..., description="Human-readable language name")
    audio_gcs_path: str = Field(..., description="GCS URI for synthesized audio track")
    video_gcs_path: Optional[str] = Field(None, description="GCS URI for muxed video containing this audio track")
    audio_size_bytes: int = Field(0, description="Size of generated audio track in bytes")
    video_size_bytes: int = Field(0, description="Size of muxed video rendition in bytes")
    segments: List[TimedDubbingSegment] = Field(default_factory=list, description="Timed dialogue translation segments")
    duration_seconds: float = Field(0.0, description="Track duration in seconds")


class DubbingJobResponse(BaseModel):
    """Full dubbing job response model."""

    job_id: str = Field(..., description="Unique dubbing job identifier")
    video_id: str = Field(..., description="Source video identifier")
    status: DubbingJobStatus = Field(..., description="Current processing status")
    config: DubbingConfigRequest = Field(..., description="Job configuration")
    tracks: Dict[str, DubbingTrackInfo] = Field(
        default_factory=dict, description="Generated language tracks keyed by language code"
    )
    source_audio_path: Optional[str] = Field(None, description="Source audio track extracted from video")
    source_dialog_path: Optional[str] = Field(
        None, description="Dialogue-only mono track extracted for ASR/translation"
    )
    error_message: Optional[str] = Field(None, description="Failure reason if job failed")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DubbingPlaybackResponse(BaseModel):
    """Signed download/playback stream URL response."""

    signed_url: str = Field(..., description="Time-limited signed GCS URL for streaming/playback")
    content_type: str = Field(..., description="MIME type e.g. video/mp4 or audio/wav")
    language: str = Field(..., description="Language code")
    media_type: str = Field("video", description="Type of media: video or audio")
    expires_in_minutes: int = Field(60, description="URL validity lifetime in minutes")
