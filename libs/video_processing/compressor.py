"""Video compression using ffmpeg."""
import logging
import ffmpeg
from pathlib import Path
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


def compress_video(
    input_path: Path,
    output_path: Path,
    resolution: Optional[str] = None,
    crf: int = 23,
    preset: str = "medium"
) -> Path:
    """
    Compress video using H.264 codec.

    Args:
        input_path: Path to input video
        output_path: Path for output video
        resolution: Target resolution (e.g., "720p", "480p", "1080p")
                   If None, uses settings.compress_resolution
        crf: Constant Rate Factor (0-51, lower is better quality, 23 is default)
        preset: Encoding preset (ultrafast, fast, medium, slow, veryslow)

    Returns:
        Path to compressed video
    """
    if resolution is None:
        resolution = settings.compress_resolution

    # Parse resolution
    height_map = {
        "360p": 360,
        "480p": 480,
        "720p": 720,
        "1080p": 1080,
        "1440p": 1440,
        "2160p": 2160,
    }
    target_height = height_map.get(resolution, 720)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        stream = ffmpeg.input(str(input_path))

        # Scale video maintaining aspect ratio
        stream = ffmpeg.filter(stream, 'scale', -2, target_height)

        # Output with H.264 codec
        stream = ffmpeg.output(
            stream,
            str(output_path),
            vcodec='libx264',
            crf=crf,
            preset=preset,
            acodec='aac',
            audio_bitrate='128k'
        )

        # Run ffmpeg
        ffmpeg.run(stream, overwrite_output=True, quiet=True)

        output_size = output_path.stat().st_size
        input_size = input_path.stat().st_size
        compression_ratio = (1 - output_size / input_size) * 100

        logger.info(
            f"Compressed {input_path.name} to {resolution}: "
            f"{input_size / 1024 / 1024:.2f}MB -> {output_size / 1024 / 1024:.2f}MB "
            f"({compression_ratio:.1f}% reduction)"
        )

        return output_path

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to compress video: {e}")
        raise
