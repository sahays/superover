from pydantic import BaseModel
from typing import List, Optional

class Track(BaseModel):
    track_type: str
    format: str
    codec: Optional[str] = None
    bit_rate: Optional[int] = None
    # Video specific
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    # Audio specific
    sampling_rate: Optional[int] = None
    channels: Optional[int] = None

class MediaMetadata(BaseModel):
    file_name: str
    file_size: int # in bytes
    duration: float # in milliseconds
    tracks: List[Track]
