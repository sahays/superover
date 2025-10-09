"""Media processor for extracting metadata, compressing video, and extracting audio."""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from libs.video_processing.metadata import extract_metadata
from libs.video_processing.compressor import compress_video
from libs.video_processing.audio import extract_audio

logger = logging.getLogger(__name__)


@dataclass
class MediaProcessingConfig:
    """Configuration for media processing."""
    compress: bool = True
    compress_resolution: str = "480p"
    extract_audio: bool = True
    audio_format: str = "mp3"
    audio_bitrate: str = "128k"
    crf: int = 23
    preset: str = "medium"


@dataclass
class MediaProcessingResult:
    """Result of media processing."""
    metadata: Dict[str, Any]
    compressed_video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    original_size_bytes: int = 0
    compressed_size_bytes: int = 0
    compression_ratio: float = 0.0
    audio_size_bytes: int = 0
    error: Optional[str] = None


class MediaProcessor:
    """Unified media processor for metadata, compression, and audio extraction."""

    def __init__(self, temp_dir: Path):
        """
        Initialize media processor.

        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        input_path: Path,
        video_id: str,
        config: MediaProcessingConfig,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> MediaProcessingResult:
        """
        Process video file with metadata extraction, compression, and audio extraction.

        Args:
            input_path: Path to input video file
            video_id: Unique video identifier
            config: Processing configuration
            progress_callback: Optional callback for progress updates (step_name, progress_percent)

        Returns:
            MediaProcessingResult with all outputs and metadata
        """
        result = MediaProcessingResult(metadata={})

        try:
            # Step 1: Extract metadata (always runs first)
            logger.info(f"[1/3] Extracting metadata for {video_id}")
            if progress_callback:
                progress_callback("extracting_metadata", 10)

            result.metadata = extract_metadata(input_path)
            result.original_size_bytes = input_path.stat().st_size

            logger.info(
                f"Metadata extracted: {result.metadata.get('duration', 0):.2f}s, "
                f"{result.metadata.get('video', {}).get('width', 0)}x"
                f"{result.metadata.get('video', {}).get('height', 0)}"
            )

            if progress_callback:
                progress_callback("extracting_metadata", 33)

            # Steps 2 & 3: Compression and audio extraction can run in parallel
            tasks = {}
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit compression task
                if config.compress:
                    logger.info(f"[2/3] Starting compression to {config.compress_resolution}")
                    compressed_path = self.temp_dir / f"{video_id}_compressed.mp4"
                    tasks['compress'] = executor.submit(
                        self._compress_video_task,
                        input_path,
                        compressed_path,
                        config
                    )

                # Submit audio extraction task
                if config.extract_audio:
                    logger.info(f"[3/3] Starting audio extraction")
                    audio_ext = config.audio_format
                    audio_path = self.temp_dir / f"{video_id}_audio.{audio_ext}"
                    tasks['audio'] = executor.submit(
                        self._extract_audio_task,
                        input_path,
                        audio_path,
                        config
                    )

                # Collect results as they complete
                for task_name, future in tasks.items():
                    try:
                        task_result = future.result()

                        if task_name == 'compress' and task_result:
                            result.compressed_video_path = task_result
                            result.compressed_size_bytes = task_result.stat().st_size
                            result.compression_ratio = (
                                1 - result.compressed_size_bytes / result.original_size_bytes
                            ) * 100 if result.original_size_bytes > 0 else 0

                            logger.info(
                                f"Compression complete: "
                                f"{result.original_size_bytes / 1024 / 1024:.2f}MB → "
                                f"{result.compressed_size_bytes / 1024 / 1024:.2f}MB "
                                f"({result.compression_ratio:.1f}% reduction)"
                            )
                            if progress_callback:
                                progress_callback("compressing", 66)

                        elif task_name == 'audio' and task_result:
                            result.audio_path = task_result
                            result.audio_size_bytes = task_result.stat().st_size
                            logger.info(
                                f"Audio extraction complete: "
                                f"{result.audio_size_bytes / 1024 / 1024:.2f}MB ({config.audio_format})"
                            )
                            if progress_callback:
                                progress_callback("extracting_audio", 66)

                    except Exception as e:
                        logger.error(f"Task {task_name} failed: {e}")
                        if result.error is None:
                            result.error = f"{task_name} failed: {str(e)}"

            if progress_callback:
                progress_callback("completed", 100)

            logger.info(f"Media processing completed for {video_id}")
            return result

        except Exception as e:
            logger.error(f"Media processing failed for {video_id}: {e}")
            result.error = str(e)
            return result

    def _compress_video_task(
        self,
        input_path: Path,
        output_path: Path,
        config: MediaProcessingConfig
    ) -> Optional[Path]:
        """
        Compression task (runs in thread).

        Args:
            input_path: Input video path
            output_path: Output compressed video path
            config: Processing configuration

        Returns:
            Path to compressed video or None if failed
        """
        try:
            compress_video(
                input_path=input_path,
                output_path=output_path,
                resolution=config.compress_resolution,
                crf=config.crf,
                preset=config.preset
            )
            return output_path
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return None

    def _extract_audio_task(
        self,
        input_path: Path,
        output_path: Path,
        config: MediaProcessingConfig
    ) -> Optional[Path]:
        """
        Audio extraction task (runs in thread).

        Args:
            input_path: Input video path
            output_path: Output audio path
            config: Processing configuration

        Returns:
            Path to extracted audio or None if failed/no audio
        """
        try:
            return extract_audio(
                input_path=input_path,
                output_path=output_path,
                audio_format=config.audio_format,
                audio_bitrate=config.audio_bitrate
            )
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return None
