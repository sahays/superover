"""Audio extraction using ffmpeg."""
import logging
import ffmpeg
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_audio(
    input_path: Path,
    output_path: Path,
    audio_format: str = "mp3",
    audio_bitrate: str = "128k"
) -> Optional[Path]:
    """
    Extract audio from video file.

    Args:
        input_path: Path to input video
        output_path: Path for output audio file
        audio_format: Audio format (mp3, aac, wav)
        audio_bitrate: Audio bitrate (e.g., "128k", "192k")

    Returns:
        Path to extracted audio file, or None if video has no audio
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if video has audio stream
        probe = ffmpeg.probe(str(input_path))
        audio_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']

        if not audio_streams:
            logger.info(f"Video {input_path.name} has no audio stream, skipping audio extraction")
            return None

        # Determine audio codec
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "wav": "pcm_s16le",
        }
        codec = codec_map.get(audio_format, "libmp3lame")

        stream = ffmpeg.input(str(input_path))
        stream = ffmpeg.output(
            stream,
            str(output_path),
            acodec=codec,
            audio_bitrate=audio_bitrate,
            vn=None  # No video
        )

        ffmpeg.run(stream, overwrite_output=True, quiet=True)

        output_size = output_path.stat().st_size
        logger.info(
            f"Extracted audio from {input_path.name}: "
            f"{output_size / 1024 / 1024:.2f}MB ({audio_format})"
        )

        return output_path

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to extract audio: {e}")
        raise
