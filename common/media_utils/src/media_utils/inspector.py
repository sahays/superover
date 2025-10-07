import json
import subprocess
from .models import MediaInfo

def inspect_media(file_path: str) -> MediaInfo:
    """
    Inspects a media file using ffprobe and returns its metadata.
    
    Args:
        file_path: The local path to the media file.
        
    Returns:
        A MediaInfo object containing the media metadata.
        
    Raises:
        Exception: If ffprobe fails or no video stream is found.
    """
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", file_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)

    video_stream = next(
        (s for s in probe_data["streams"] if s["codec_type"] == "video"),
        None
    )
    if not video_stream:
        raise Exception("No video stream found in the file.")

    return MediaInfo(
        duration=float(probe_data["format"]["duration"]),
        file_size=int(probe_data["format"]["size"]),
        bitrate=int(probe_data["format"].get("bit_rate", 0)),
        resolution=f"{video_stream['width']}x{video_stream['height']}",
        codec=video_stream["codec_name"]
    )
