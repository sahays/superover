import subprocess
from pathlib import Path
from .models import AudioExtractionResult

def extract_audio(video_path: str, output_path: str) -> AudioExtractionResult:
    """
    Extracts the audio from a video file into WAV format.
    
    Args:
        video_path: The local path to the source video.
        output_path: The local path to write the extracted audio to.
        
    Returns:
        An AudioExtractionResult object with details of the operation.
        
    Raises:
        Exception: If ffmpeg fails.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
        "-ar", "44100", "-ac", "2", "-y", output_path
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Get audio duration from ffprobe
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", output_path
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)
    duration = float(probe_data["format"]["duration"])

    return AudioExtractionResult(
        audioPath=output_path,
        gcsPath="", # GCS path will be set by the caller
        duration=duration,
        format="wav"
    )
