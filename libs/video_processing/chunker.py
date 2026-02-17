"""Video chunking using ffmpeg."""

import logging
import ffmpeg
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)


def chunk_video(
    input_path: Path,
    output_dir: Path,
    chunk_duration: Optional[int] = None,
    prefix: str = "chunk",
    expected_duration: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Split video or audio file into chunks of specified duration.

    Args:
        input_path: Path to input video or audio file
        output_dir: Directory for output chunks
        chunk_duration: Duration of each chunk in seconds
                       If None, uses settings.chunk_duration_seconds
        prefix: Prefix for chunk filenames
        expected_duration: Expected duration in seconds (overrides probe if provided)
                          Useful when probe returns incorrect duration for some audio formats

    Returns:
        List of chunk info dictionaries with paths and timestamps
    """
    if chunk_duration is None:
        chunk_duration = settings.chunk_duration_seconds

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get media duration and detect if it's audio or video
        probe = ffmpeg.probe(str(input_path))
        probed_duration = float(probe["format"]["duration"])

        # Use expected duration if provided, otherwise use probed duration
        duration = expected_duration if expected_duration is not None else probed_duration

        if expected_duration is not None and abs(probed_duration - expected_duration) > 1.0:
            logger.warning(
                f"Duration mismatch for {input_path.name}: "
                f"probed={probed_duration:.2f}s, expected={expected_duration:.2f}s. "
                f"Using expected duration."
            )

        # Detect if input is audio-only or video
        has_video = any(stream["codec_type"] == "video" for stream in probe["streams"])
        input_extension = input_path.suffix.lower()

        # Determine output format
        if has_video or input_extension in [".mp4", ".mov", ".avi", ".mkv"]:
            output_extension = ".mp4"
            codec_args = {"vcodec": "copy", "acodec": "copy"}
        else:
            # Audio-only file - keep original format or use a common one
            if input_extension in [".mp3", ".m4a", ".aac", ".wav", ".ogg"]:
                output_extension = input_extension
            else:
                output_extension = ".aac"  # Default for unknown audio formats
            codec_args = {"acodec": "copy"}

        chunks = []
        start_time = 0
        chunk_index = 0

        while start_time < duration:
            end_time = min(start_time + chunk_duration, duration)
            chunk_filename = f"{prefix}_{chunk_index:04d}{output_extension}"
            chunk_path = output_dir / chunk_filename

            # Extract chunk
            stream = ffmpeg.input(str(input_path), ss=start_time, t=chunk_duration)
            stream = ffmpeg.output(stream, str(chunk_path), avoid_negative_ts="make_zero", **codec_args)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            chunk_info = {
                "index": chunk_index,
                "filename": chunk_filename,
                "path": str(chunk_path),
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "size_bytes": chunk_path.stat().st_size,
            }
            chunks.append(chunk_info)

            media_type = "video" if has_video else "audio"
            logger.info(
                f"Created {media_type} chunk {chunk_index}: {start_time:.2f}s - {end_time:.2f}s "
                f"({chunk_path.stat().st_size / 1024 / 1024:.2f}MB)"
            )

            start_time = end_time
            chunk_index += 1

        media_type = "video" if has_video else "audio"
        logger.info(f"Split {media_type} file {input_path.name} into {len(chunks)} chunks")
        return chunks

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to chunk video: {e}")
        raise
