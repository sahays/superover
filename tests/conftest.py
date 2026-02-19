"""Pytest configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from google.cloud import firestore
from google.cloud import storage


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore client."""
    mock_client = MagicMock(spec=firestore.Client)
    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection
    return mock_client


@pytest.fixture
def mock_storage_client():
    """Mock GCS storage client."""
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    return mock_client


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_metadata():
    """Sample video metadata."""
    return {
        "video_id": "test-video-123",
        "filename": "test_video.mp4",
        "gcs_path": "gs://test-bucket/test_video.mp4",
        "content_type": "video/mp4",
        "size_bytes": 1024000,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "metadata": {"duration": 60.0, "width": 1920, "height": 1080, "fps": 30.0},
    }


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "summary": "A test video scene",
        "scene_description": "Test scene description",
        "objects": [
            {
                "name": "person",
                "timestamp_start": "00:00:05",
                "timestamp_end": "00:00:15",
                "confidence": 0.95,
                "description": "Person walking",
            }
        ],
        "camera_movement": [
            {
                "type": "static",
                "timestamp_start": "00:00:00",
                "timestamp_end": "00:00:30",
                "description": "Static camera",
            }
        ],
        "characters": [],
        "dialogues": [],
        "audio_description": {
            "background_music": "None",
            "sound_effects": [],
            "ambient_sounds": "None",
        },
        "moderation": {
            "violence": {"detected": False, "severity": "none"},
            "adult_content": {"detected": False, "severity": "none"},
            "profanity": {"detected": False},
            "sensitive_content": {"detected": False},
        },
        "scene_changes": [],
        "visual_style": {
            "lighting": "natural",
            "color_palette": "neutral tones",
            "composition": "centered",
        },
        "context_tags": ["test", "sample"],
    }
