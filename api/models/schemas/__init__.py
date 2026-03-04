"""Pydantic models for API requests and responses — re-exports all schemas."""

from .shared import (
    SignedUrlRequest,
    SignedUrlResponse,
    CreateVideoRequest,
    ContextItemRequest,
    ProcessVideoRequest,
    VideoResponse,
    ManifestResponse,
    ProcessingJobResponse,
    ResultResponse,
    HealthResponse,
)
from .media import (
    MediaProcessingConfigRequest,
    CreateMediaJobRequest,
    MediaJobResultsResponse,
    MediaJobResponse,
    MediaPresetResponse,
)
from .scenes import (
    SceneAnalysisRequest,
    AnalyzeVideoRequest,
    SceneAnalysisJobResponse,
    AnalysisJobResponse,
    SceneProcessingConfigRequest,
    SceneJobResultsResponse,
    SceneJobResponse,
)
from .prompts import (
    PROMPT_TYPES,
    PromptResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
)
from .images import (
    ImageProcessingConfigRequest,
    CreateImageJobRequest,
    ImageJobResponse,
)
from .category import (
    CategorySchemaResponse,
    SetCategorySchemaRequest,
)
from .branding import (
    BrandingResponse,
    UpdateBrandingRequest,
)
from .search import (
    SyncStatusItem,
    SyncRequest,
    SyncResponse,
    SearchRequest,
    VideoSearchResult,
    InVideoSearchResult,
    SearchRecommendation,
    CuratedSearchResponse,
)

__all__ = [
    # Shared
    "SignedUrlRequest",
    "SignedUrlResponse",
    "CreateVideoRequest",
    "ContextItemRequest",
    "ProcessVideoRequest",
    "VideoResponse",
    "ManifestResponse",
    "ProcessingJobResponse",
    "ResultResponse",
    "HealthResponse",
    # Media
    "MediaProcessingConfigRequest",
    "CreateMediaJobRequest",
    "MediaJobResultsResponse",
    "MediaJobResponse",
    "MediaPresetResponse",
    # Scenes
    "SceneAnalysisRequest",
    "AnalyzeVideoRequest",
    "SceneAnalysisJobResponse",
    "AnalysisJobResponse",
    "SceneProcessingConfigRequest",
    "SceneJobResultsResponse",
    "SceneJobResponse",
    # Prompts
    "PROMPT_TYPES",
    "PromptResponse",
    "CreatePromptRequest",
    "UpdatePromptRequest",
    # Images
    "ImageProcessingConfigRequest",
    "CreateImageJobRequest",
    "ImageJobResponse",
    # Category
    "CategorySchemaResponse",
    "SetCategorySchemaRequest",
    # Branding
    "BrandingResponse",
    "UpdateBrandingRequest",
    # Search
    "SyncStatusItem",
    "SyncRequest",
    "SyncResponse",
    "SearchRequest",
    "VideoSearchResult",
    "InVideoSearchResult",
    "SearchRecommendation",
    "CuratedSearchResponse",
]
