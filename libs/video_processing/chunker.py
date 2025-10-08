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
    prefix: str = "chunk"
) -> List[Dict[str, Any]]:
    """
    Split video into chunks of specified duration.

    Args:
        input_path: Path to input video
        output_dir: Directory for output chunks
        chunk_duration: Duration of each chunk in seconds
                       If None, uses settings.chunk_duration_seconds
        prefix: Prefix for chunk filenames

    Returns:
        List of chunk info dictionaries with paths and timestamps
    """
    if chunk_duration is None:
        chunk_duration = settings.chunk_duration_seconds

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get video duration
        probe = ffmpeg.probe(str(input_path))
        duration = float(probe['format']['duration'])

        chunks = []
        start_time = 0
        chunk_index = 0

        while start_time < duration:
            end_time = min(start_time + chunk_duration, duration)
            chunk_filename = f"{prefix}_{chunk_index:04d}.mp4"
            chunk_path = output_dir / chunk_filename

            # Extract chunk
            stream = ffmpeg.input(str(input_path), ss=start_time, t=chunk_duration)
            stream = ffmpeg.output(
                stream,
                str(chunk_path),
                vcodec='copy',
                acodec='copy',
                avoid_negative_ts='make_zero'
            )
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            chunk_info = {
                "index": chunk_index,
                "filename": chunk_filename,
                "path": str(chunk_path),
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "size_bytes": chunk_path.stat().st_size
            }
            chunks.append(chunk_info)

            logger.info(
                f"Created chunk {chunk_index}: {start_time:.2f}s - {end_time:.2f}s "
                f"({chunk_path.stat().st_size / 1024 / 1024:.2f}MB)"
            )

            start_time = end_time
            chunk_index += 1

        logger.info(f"Split {input_path.name} into {len(chunks)} chunks")
        return chunks

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to chunk video: {e}")
        raise
