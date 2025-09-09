from pydantic import BaseModel
from typing import Optional, List

class AudioExtractionRequest(BaseModel):
    video_file_path: str
    output_directory: Optional[str] = None # Directory to save files in

class ExtractedTrack(BaseModel):
    track_index: int
    output_path: str

class AudioExtractionResult(BaseModel):
    input_video_path: str
    combined_audio_path: str
    individual_tracks: List[ExtractedTrack]
    status: str
    message: str
