from pydantic import BaseModel
from typing import Optional, List

class VideoProcessingRequest(BaseModel):
    video_file_path: str
    output_directory: Optional[str] = None
    split_timestamps: Optional[str] = None # e.g., "00:10-00:20,01:30-01:45"
    chunk_duration: Optional[int] = None   # e.g., 5 (in seconds)
    compress_resolution: Optional[str] = None # e.g., "1280x720"
    compress_first: Optional[bool] = False

class ProcessedFile(BaseModel):
    output_path: str
    source_operation: str # e.g., "split", "chunk", "compress"

class VideoProcessingResult(BaseModel):
    input_video_path: str
    operations_performed: List[str]
    output_files: List[ProcessedFile]
    status: str
    message: str
    time_taken_seconds: float
