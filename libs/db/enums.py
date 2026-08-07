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


class EngagementJobStatus(str, Enum):
    """Engagement analysis job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DubbingJobStatus(str, Enum):
    """Dubbing job processing stages."""

    PENDING = "pending"
    EXTRACTING_AUDIO = "extracting_audio"
    DUBBING_TRANSLATION = "dubbing_translation"
    GENERATING_SPEECH = "generating_speech"
    MUXING_VIDEO = "muxing_video"
    COMPLETED = "completed"
    FAILED = "failed"


class DubbingLanguage(str, Enum):
    """Supported dubbing target languages."""

    HINDI = "hi-IN"
    ENGLISH = "en-US"
    PORTUGUESE = "pt-BR"
    SPANISH = "es-ES"
    GERMAN = "de-DE"


class DubbingMode(str, Enum):
    """Dubbing audio mixing strategies."""

    VOICEOVER = "voiceover"  # Duck original background audio and overlay dubbed track
    REPLACE = "replace"      # Clean replacement of original speech dialogue
    ISOLATED = "isolated"    # Output isolated speech audio track only

