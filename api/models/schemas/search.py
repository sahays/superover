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


class VideoSearchResult(BaseModel):
    """A cross-video search result (one per video)."""

    video_id: str
    video_filename: Optional[str] = None
    top_match_text: str
    score: float
    chunk_count: int = 1
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None


class InVideoSearchResult(BaseModel):
    """A within-video search result (timestamped moment)."""

    chunk_index: Optional[int] = None
    text_content: str
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    score: float
