import os
import json
import subprocess
from pathlib import Path
from typing import List
from .models import Chunk, CompressionResult

def compress_video(input_path: str, output_path: str, resolution: str) -> CompressionResult:
    """
    Compresses a video to a specified resolution using ffmpeg.
    
    Args:
        input_path: The local path to the source video.
        output_path: The local path to write the compressed video to.
        resolution: The target resolution (e.g., "720p", "1080p").
        
    Returns:
        A CompressionResult object with details of the operation.
        
    Raises:
        Exception: If ffmpeg fails.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    original_size = os.path.getsize(input_path)

    scale_map = {
        "480p": "scale=854:480",
        "720p": "scale=1280:720",
        "1080p": "scale=1920:1080"
    }
    scale_filter = scale_map.get(resolution, "scale=1280:720") # Default to 720p

    cmd = [
        "ffmpeg", "-i", input_path, "-vf", scale_filter,
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-y", output_path
    ]

    subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    compressed_size = os.path.getsize(output_path)

    return CompressionResult(
        compressedPath=output_path,
        gcsPath="", # GCS path will be set by the caller
        originalSize=original_size,
        compressedSize=compressed_size
    )

def chunk_video(video_path: str, output_dir: str, chunk_duration: int) -> List[Chunk]:
    """
    Splits a video into smaller chunks of a specified duration.
    
    Args:
        video_path: The local path to the video file.
        output_dir: The directory to save the video chunks.
        chunk_duration: The duration of each chunk in seconds.
        
    Returns:
        A list of Chunk objects, each representing a video segment.
        
    Raises:
        Exception: If ffprobe or ffmpeg fails.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Get video duration from ffprobe
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", video_path
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)
    total_duration = float(probe_data["format"]["duration"])

    chunks = []
    start_time = 0
    index = 0

    while start_time < total_duration:
        end_time = min(start_time + chunk_duration, total_duration)
        chunk_filename = f"chunk_{index:04d}.mp4"
        chunk_path = os.path.join(output_dir, chunk_filename)

        cmd = [
            "ffmpeg", "-i", video_path, "-ss", str(start_time),
            "-t", str(end_time - start_time), "-c", "copy",
            "-y", chunk_path
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        chunks.append(Chunk(
            index=index,
            localPath=chunk_path,
            gcsPath="", # GCS path will be set by the caller
            startTime=start_time,
            endTime=end_time
        ))

        index += 1
        start_time = end_time
        
    return chunks
