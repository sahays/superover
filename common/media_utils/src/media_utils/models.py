from pydantic import BaseModel
from typing import List, Optional

class MediaInfo(BaseModel):
    """Represents the metadata of a media file."""
    duration: float
    resolution: str
    codec: str
    fileSize: int
    bitrate: int

class CompressionResult(BaseModel):
    """Represents the result of a video compression operation."""
    compressedPath: str
    gcsPath: str
    originalSize: int
    compressedSize: int

class Chunk(BaseModel):
    """Represents a single chunk of a video."""
    index: int
    localPath: str
    gcsPath: str
    startTime: float
    endTime: float

class VideoChunkingResult(BaseModel):
    """Represents the result of a video chunking operation."""
    chunks: List[Chunk]
    manifestPath: str
    totalChunks: int

class AudioExtractionResult(BaseModel):
    """Represents the result of an audio extraction operation."""
    audioPath: str
    gcsPath: str
    duration: float
    format: str

class Scene(BaseModel):
    """Represents a single scene detected in a video."""
    startTime: float
    endTime: float
    description: str
    confidence: float
    chunkIndex: int

class SceneAnalysisResult(BaseModel):
    """Represents the result of a scene analysis operation."""
    analysisPath: str
    scenes: List[Scene]
    totalScenes: int
