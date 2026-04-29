"""Engagement analysis API schemas."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


_ALLOWED_BARC_PREFIXES = ("text/csv", "application/csv", "application/vnd.ms-excel", "text/plain")


class BarcSignedUrlRequest(BaseModel):
    """Signed-URL request for a BARC CSV upload (looser content-type than media uploads)."""

    filename: str = Field(..., description="CSV filename")
    content_type: str = Field(..., description="Must be a CSV-ish MIME type")

    @field_validator("content_type")
    @classmethod
    def _validate(cls, v: str) -> str:
        if not v.startswith(_ALLOWED_BARC_PREFIXES):
            raise ValueError(f"BARC upload must be a CSV. Got: {v}")
        return v


class CreateEngagementJobRequest(BaseModel):
    """Request to start an engagement analysis job."""

    video_id: str = Field(..., description="Video ID this analysis is for")
    source_scene_job_id: str = Field(..., description="Completed scene_analysis job whose results provide context")
    barc_gcs_path: str = Field(..., description="GCS path to the uploaded BARC CSV")
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional overrides (e.g. peak count, min spacing)"
    )


class EngagementExtremum(BaseModel):
    rank: int
    timestamp_sec: float
    score: Optional[float] = None
    scene_summary: Optional[str] = None
    explanation: Optional[str] = None
    chunk_index: Optional[int] = None
    key_actors: Optional[List[str]] = None
    key_events: Optional[List[str]] = None
    key_objects: Optional[List[str]] = None


class EngagementResults(BaseModel):
    peaks: List[EngagementExtremum] = []
    valleys: List[EngagementExtremum] = []
    timeseries_gcs_path: Optional[str] = None
    barc_time_column: Optional[str] = None
    barc_score_column: Optional[str] = None
    point_count: Optional[int] = None
    duration_sec: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class EngagementJobResponse(BaseModel):
    job_id: str
    video_id: str
    source_scene_job_id: str
    barc_gcs_path: str
    status: str
    config: Optional[Dict[str, Any]] = None
    results: Optional[EngagementResults] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None


class EligibleSourceJob(BaseModel):
    """A completed scene_analysis job eligible to drive engagement analysis."""

    job_id: str
    video_id: str
    prompt_name: Optional[str] = None
    prompt_type: Optional[str] = None
    created_at: Optional[datetime] = None


class EngagementTimeseriesResponse(BaseModel):
    points: List[List[float]] = Field(..., description="List of [timestamp_sec, score] pairs")
    time_column: Optional[str] = None
    score_column: Optional[str] = None
