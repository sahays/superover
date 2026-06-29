"""
Centralized configuration module.
Designed to work both locally and on Cloud Run.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Service Naming
    service_name: str = "superover"

    # GCP Configuration
    gcp_project_id: str
    gcp_region: str = "asia-south1"

    # GCS Buckets
    uploads_bucket: str
    processed_bucket: str
    results_bucket: str

    # Gemini API (uses ADC — no API key needed on Cloud Run)
    gemini_region: str = "global"  # Gemini endpoint region (separate from gcp_region)
    gemini_default_model: str = "gemini-3.1-pro-preview"
    gemini_default_output_tokens: int = 65536
    gemini_temperature: float = 1.0
    gemini_image_model: str = "gemini-3-pro-image-preview"
    gemini_image_output_tokens: int = 32768

    # Firestore
    firestore_database: str = "(default)"

    # BigQuery (Natural Language Search)
    bq_dataset: str = "superover_search"

    # Gemini Search Curation
    gemini_search_model: str = "gemini-3.5-flash"
    gemini_search_output_tokens: int = 8192

    # Environment
    environment: str = "local"  # local, development, production

    # Video Processing
    max_video_size_mb: int = 500
    chunk_duration_seconds: int = 30
    compress_resolution: str = "480p"  # 480p for faster processing
    temp_storage_path: Path = Path("./storage/temp")

    # Speech-to-Text (Chirp 3)
    chirp_model: str = "chirp_3"
    chirp_language: str = "auto"  # "auto" for auto-detect, or e.g. "en-US"

    # Transcoder API
    transcoder_location: str = "asia-south1"  # Must match GCS bucket region
    transcoder_job_timeout_seconds: int = 600

    # Worker Settings
    worker_poll_interval_seconds: int = 5
    max_concurrent_tasks: int = 3

    # Scene Processing Settings
    scene_processing_mode: str = "sequential"  # "sequential" or "parallel"
    max_gemini_workers: int = 10  # Max concurrent Gemini API calls in parallel mode

    # Auth
    master_invite_code: str = ""

    # Avatar Live (Vertex Gemini Live preview). avatar_live_project must be
    # set explicitly — the preview surface is allowlisted per project.
    avatar_live_model: str = "gemini-3.1-flash-live-preview-04-2026"
    avatar_live_project: str = ""
    avatar_live_location: str = "global"
    avatar_live_preset_name: Optional[str] = None
    avatar_live_audio_only: bool = False
    # Override the default Vertex Live host (e.g. when the model graduates
    # from the autopush sandbox to GA aiplatform.googleapis.com).
    avatar_live_host_override: Optional[str] = None
    # Per-frame relay logging for the live session — noisy, off by default.
    avatar_live_debug: bool = False

    # Runtime
    port: int = 8080  # Cloud Run uses 8080 by default

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.environment == "local"

    def is_cloud_run(self) -> bool:
        """Check if running on Cloud Run."""
        return os.getenv("K_SERVICE") is not None

    def get_temp_dir(self) -> Path:
        """Get temp directory, creating if needed."""
        temp_dir = self.temp_storage_path
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use this function throughout the application.
    """
    return Settings()


# Convenience exports
settings = get_settings()
