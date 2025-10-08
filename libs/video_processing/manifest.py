"""Manifest creation for processed video assets."""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def create_manifest(
    video_id: str,
    original_metadata: Dict[str, Any],
    compressed_path: Optional[str] = None,
    chunks: Optional[List[Dict[str, Any]]] = None,
    audio_path: Optional[str] = None,
    processing_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a processing manifest for a video.

    This manifest serves as the source of truth for all processed assets
    and can be used by downstream analysis tasks.

    Args:
        video_id: Unique video identifier
        original_metadata: Metadata from the original video
        compressed_path: GCS path to compressed video
        chunks: List of chunk information dictionaries
        audio_path: GCS path to extracted audio
        processing_metadata: Additional processing information

    Returns:
        Manifest dictionary
    """
    manifest = {
        "video_id": video_id,
        "version": "1.0",
        "original": original_metadata,
    }

    if compressed_path:
        manifest["compressed"] = {
            "gcs_path": compressed_path,
        }

    if chunks:
        manifest["chunks"] = {
            "count": len(chunks),
            "duration_per_chunk": chunks[0]["duration"] if chunks else 0,
            "items": chunks,
        }

    if audio_path:
        manifest["audio"] = {
            "gcs_path": audio_path,
            "format": "mp3",
        }

    if processing_metadata:
        manifest["processing"] = processing_metadata

    logger.info(f"Created manifest for video {video_id}: {len(chunks or [])} chunks")
    return manifest
