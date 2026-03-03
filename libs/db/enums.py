"""Database status enums."""

from enum import Enum


class MediaJobStatus(str, Enum):
    """Media processing job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    TRANSCODING = "transcoding"
    COMPLETED = "completed"
    FAILED = "failed"


class SceneJobStatus(str, Enum):
    """Scene analysis job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ImageJobStatus(str, Enum):
    """Image adaptation job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
