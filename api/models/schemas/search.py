"""Search and sync schemas for BigQuery AI.SEARCH integration."""

from typing import Optional, List
from pydantic import BaseModel, Field


# === Sync Models ===


class SyncStatusItem(BaseModel):
    """A scene result with its sync status.

    sync_status values:
      not_synced — not yet pushed to BigQuery
      pending    — inserted into BigQuery, embedding generating
      ready      — embedding generated, searchable
      error      — embedding generation failed
    """

    result_id: str
    video_id: str
    video_filename: Optional[str] = None
    scene_job_id: Optional[str] = None
    chunk_index: Optional[int] = None
    sync_status: str = "not_synced"
    sync_error: Optional[str] = None
    text_preview: Optional[str] = None
    text_content: Optional[str] = None
    created_at: Optional[str] = None


class SyncRequest(BaseModel):
    """Request to sync scene results to BigQuery."""

    result_ids: List[str] = Field(..., description="IDs of scene results to sync")
    resync: bool = Field(False, description="If true, re-index already-synced results with fresh text")


class SyncResponse(BaseModel):
    """Response after syncing scene results."""

    synced_count: int = 0
    errors: List[str] = Field(default_factory=list)


# === Search Models ===


class SearchRequest(BaseModel):
    """Request for semantic search."""

    query: str = Field(..., description="Natural language search query")
    limit: int = Field(20, ge=1, le=100, description="Max results to return")
    audio: Optional[str] = Field(None, description="Base64-encoded audio (max ~10s)")
    audio_mime: Optional[str] = Field(None, description="Audio MIME type, e.g. audio/webm")


class VideoSearchResult(BaseModel):
    """A cross-video search result (one per video)."""

    video_id: str
    video_filename: Optional[str] = None
    top_match_text: str
    score: float
    chunk_count: int = 1
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    content_type: Optional[str] = None
    mood: Optional[str] = None
    setting: Optional[str] = None
    actors: Optional[List[str]] = None


class InVideoSearchResult(BaseModel):
    """A within-video search result (timestamped moment)."""

    chunk_index: Optional[int] = None
    text_content: str
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    score: float


# === Curated Search Models ===


class SearchRecommendation(BaseModel):
    """A Gemini-curated search recommendation."""

    video_id: str
    video_filename: Optional[str] = None
    gcs_path: Optional[str] = None
    recommendation_type: str = Field(description="full_video or clip")
    title: str
    reason: str
    clip_start: Optional[str] = None
    clip_end: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class CuratedSearchResponse(BaseModel):
    """Gemini-curated search response with recommendations and raw results."""

    response_text: str
    recommendations: List[SearchRecommendation] = Field(default_factory=list)
    raw_results: List[VideoSearchResult] = Field(default_factory=list)
    interpreted_query: Optional[str] = Field(None, description="English query produced by the interpreter")
