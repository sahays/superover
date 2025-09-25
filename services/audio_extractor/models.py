from pydantic import BaseModel
from typing import Optional, List

class AudioExtractionRequest(BaseModel):
    video_file_path: str
    output_directory: Optional[str] = None

class ExtractedChannel(BaseModel):
    channel_index: int
    output_path: str

class ExtractedTrack(BaseModel):
    track_index: int
    channels: int
    channel_layout: str
    extracted_channels: List[ExtractedChannel]

class AudioExtractionResult(BaseModel):
    input_video_path: str
    combined_audio_path: Optional[str] = None
    individual_tracks: List[ExtractedTrack]
    status: str
    message: str
