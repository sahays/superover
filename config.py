"""
Centralized configuration module.
Designed to work both locally and on Cloud Run.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # GCP Configuration
    gcp_project_id: str
    gcp_region: str = "asia-south1"

    # GCS Buckets
    uploads_bucket: str
    processed_bucket: str
    results_bucket: str

    # Gemini API
    gemini_api_key: str
    gemini_model: str = "models/gemini-2.0-flash-exp"

    # Firestore
    firestore_database: str = "(default)"

    # URLs (different for local vs Cloud Run)
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # Environment
    environment: str = "local"  # local, development, production

    # Video Processing
    max_video_size_mb: int = 500
    chunk_duration_seconds: int = 30
    compress_resolution: str = "480p"  # 480p for faster processing
    temp_storage_path: Path = Path("./storage/temp")

    # Worker Settings
    worker_poll_interval_seconds: int = 5
    max_concurrent_tasks: int = 3

    # Scene Processing Settings
    scene_processing_mode: str = "sequential"  # "sequential" or "parallel"
    max_gemini_workers: int = 10  # Max concurrent Gemini API calls in parallel mode

    # Runtime
    port: int = 8080  # Cloud Run uses 8080 by default

    class Config:
        env_file = ".env"
        case_sensitive = False

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
