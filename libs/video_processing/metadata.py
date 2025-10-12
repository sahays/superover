"""Video metadata extraction using ffmpeg."""
import json
import logging
import ffmpeg
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def extract_metadata(video_path: Path) -> Dict[str, Any]:
    """
    Extract metadata from video file using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Dictionary with video metadata
    """
    try:
        probe = ffmpeg.probe(str(video_path))

        video_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
            None
        )
        audio_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
            None
        )

        metadata = {
            "format": probe['format']['format_name'],
            "duration": float(probe['format'].get('duration', 0)),
            "size_bytes": int(probe['format'].get('size', 0)),
            "bit_rate": int(probe['format'].get('bit_rate', 0)),
        }

        if video_stream:
            metadata["video"] = {
                "codec": video_stream.get('codec_name'),
                "width": int(video_stream.get('width', 0)),
                "height": int(video_stream.get('height', 0)),
                "fps": eval(video_stream.get('r_frame_rate', '0/1')),
                "bit_rate": int(video_stream.get('bit_rate', 0)) if 'bit_rate' in video_stream else None,
            }

        if audio_stream:
            metadata["audio"] = {
                "codec": audio_stream.get('codec_name'),
                "sample_rate": int(audio_stream.get('sample_rate', 0)),
                "channels": int(audio_stream.get('channels', 0)),
                "bit_rate": int(audio_stream.get('bit_rate', 0)) if 'bit_rate' in audio_stream else None,
            }

        # Log appropriate message based on media type
        if video_stream:
            logger.info(f"Extracted video metadata from {video_path.name}: {metadata['duration']:.2f}s, {metadata['video']['width']}x{metadata['video']['height']}")
        elif audio_stream:
            logger.info(f"Extracted audio metadata from {video_path.name}: {metadata['duration']:.2f}s, {metadata['audio']['channels']} channels")
        else:
            logger.warning(f"No video or audio streams found in {video_path.name}")

        return metadata

    except Exception as e:
        logger.error(f"Failed to extract metadata from {video_path}: {e}")
        raise
