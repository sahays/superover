"""Media processor for extracting metadata, compressing video, and extracting audio."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

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
    audio_sample_rate: str = "22050"  # For audio compression (speech: 16000 or 22050)
    audio_channels: int = 1  # 1=mono, 2=stereo (mono recommended for speech)
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

    def detect_media_type(self, input_path: Path) -> str:
        """
        Detect if file is video, audio, or image using metadata.

        Args:
            input_path: Path to media file

        Returns:
            'video', 'audio', or 'image'
        """
        try:
            metadata = extract_metadata(input_path)
            # If video stream exists, check if it's a still image or actual video
            if metadata.get("video"):
                # Some images are detected as having a single frame video stream
                format_name = metadata.get("format", {}).get("format_name", "").lower()
                if any(img_fmt in format_name for img_fmt in ["image2", "png", "jpeg", "webp"]):
                    return "image"
                return "video"
            # If only audio stream exists, it's audio
            elif metadata.get("audio"):
                return "audio"
            else:
                # Fallback based on extension
                ext = input_path.suffix.lower()
                if ext in [".jpg", ".jpeg", ".png", ".webp", ".tiff"]:
                    return "image"
                return "video"
        except Exception as e:
            logger.warning(f"Could not detect media type: {e}, assuming video")
            return "video"

    def process(
        self,
        input_path: Path,
        video_id: str,
        config: MediaProcessingConfig,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> MediaProcessingResult:
        """
        Process media file (video, audio, or image) with appropriate operations.

        Args:
            input_path: Path to input media file
            video_id: Unique media identifier
            config: Processing configuration
            progress_callback: Optional callback for progress updates (step_name, progress_percent)

        Returns:
            MediaProcessingResult with all outputs and metadata
        """
        # Detect media type
        media_type = self.detect_media_type(input_path)
        logger.info(f"Detected media type: {media_type}")

        # Route to appropriate processor
        if media_type == "audio":
            return self._process_audio(input_path, video_id, config, progress_callback)
        elif media_type == "image":
            return self._process_image(input_path, video_id, config, progress_callback)
        else:
            return self._process_video(input_path, video_id, config, progress_callback)

    def _process_image(
        self,
        input_path: Path,
        video_id: str,
        config: MediaProcessingConfig,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> MediaProcessingResult:
        """
        Process image file with metadata extraction and optional optimization.
        """
        result = MediaProcessingResult(metadata={})
        try:
            if progress_callback:
                progress_callback("extracting_metadata", 20)

            result.metadata = extract_metadata(input_path)
            result.original_size_bytes = input_path.stat().st_size

            if progress_callback:
                progress_callback("completed", 100)

            return result
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            result.error = str(e)
            return result

    def _process_video(
        self,
        input_path: Path,
        video_id: str,
        config: MediaProcessingConfig,
        progress_callback: Optional[Callable[[str, int], None]] = None,
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

            # Steps 2 & 3: Run compression first, then audio extraction
            # Step 2: Compression
            if config.compress:
                logger.info(f"[2/3] Starting compression to {config.compress_resolution}")
                if progress_callback:
                    progress_callback("compressing", 40)

                compressed_path = self.temp_dir / f"{video_id}_compressed.mp4"
                try:
                    compress_result = self._compress_video_task(input_path, compressed_path, config)
                    if compress_result:
                        result.compressed_video_path = compress_result
                        result.compressed_size_bytes = compress_result.stat().st_size
                        result.compression_ratio = (
                            (1 - result.compressed_size_bytes / result.original_size_bytes) * 100
                            if result.original_size_bytes > 0
                            else 0
                        )

                        logger.info(
                            f"Compression complete: "
                            f"{result.original_size_bytes / 1024 / 1024:.2f}MB → "
                            f"{result.compressed_size_bytes / 1024 / 1024:.2f}MB "
                            f"({result.compression_ratio:.1f}% reduction)"
                        )
                        if progress_callback:
                            progress_callback("compressing", 66)
                except Exception as e:
                    logger.error(f"Compression failed: {e}")
                    if result.error is None:
                        result.error = f"Compression failed: {str(e)}"

            # Step 3: Audio extraction
            if config.extract_audio:
                logger.info("[3/3] Starting audio extraction")
                if progress_callback:
                    progress_callback("extracting_audio", 70)

                audio_ext = config.audio_format
                audio_path = self.temp_dir / f"{video_id}_audio.{audio_ext}"
                try:
                    audio_result = self._extract_audio_task(input_path, audio_path, config)
                    if audio_result:
                        result.audio_path = audio_result
                        result.audio_size_bytes = audio_result.stat().st_size
                        logger.info(
                            f"Audio extraction complete: "
                            f"{result.audio_size_bytes / 1024 / 1024:.2f}MB ({config.audio_format})"
                        )
                        if progress_callback:
                            progress_callback("extracting_audio", 90)
                except Exception as e:
                    logger.error(f"Audio extraction failed: {e}")
                    if result.error is None:
                        result.error = f"Audio extraction failed: {str(e)}"

            if progress_callback:
                progress_callback("completed", 100)

            logger.info(f"Media processing completed for {video_id}")
            return result

        except Exception as e:
            logger.error(f"Media processing failed for {video_id}: {e}")
            result.error = str(e)
            return result

    def _process_audio(
        self,
        input_path: Path,
        video_id: str,
        config: MediaProcessingConfig,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> MediaProcessingResult:
        """
        Process audio file with metadata extraction and optional format conversion.

        Args:
            input_path: Path to input audio file
            video_id: Unique audio identifier
            config: Processing configuration
            progress_callback: Optional callback for progress updates

        Returns:
            MediaProcessingResult with audio output and metadata
        """
        result = MediaProcessingResult(metadata={})

        try:
            # Step 1: Extract metadata
            logger.info(f"[1/2] Extracting audio metadata for {video_id}")
            if progress_callback:
                progress_callback("extracting_metadata", 20)

            result.metadata = extract_metadata(input_path)
            result.original_size_bytes = input_path.stat().st_size

            logger.info(
                f"Audio metadata extracted: {result.metadata.get('duration', 0):.2f}s, "
                f"{result.metadata.get('audio', {}).get('bitrate', 'unknown')} bitrate"
            )

            if progress_callback:
                progress_callback("extracting_metadata", 40)

            # Step 2: Convert/compress audio (always do this for optimization)
            logger.info(f"[2/2] Converting audio to {config.audio_format} @ {config.audio_bitrate}")
            if progress_callback:
                progress_callback("converting_audio", 50)

            audio_ext = config.audio_format
            audio_path = self.temp_dir / f"{video_id}_audio.{audio_ext}"

            try:
                audio_result = self._extract_audio_task(input_path, audio_path, config)
                if audio_result:
                    result.audio_path = audio_result
                    result.audio_size_bytes = audio_result.stat().st_size
                    result.compression_ratio = (
                        (1 - result.audio_size_bytes / result.original_size_bytes) * 100
                        if result.original_size_bytes > 0
                        else 0
                    )

                    logger.info(
                        f"Audio conversion complete: "
                        f"{result.original_size_bytes / 1024 / 1024:.2f}MB → "
                        f"{result.audio_size_bytes / 1024 / 1024:.2f}MB "
                        f"({result.compression_ratio:.1f}% reduction)"
                    )
                    if progress_callback:
                        progress_callback("converting_audio", 90)
                else:
                    # If conversion failed, use original file
                    result.audio_path = input_path
                    result.audio_size_bytes = result.original_size_bytes
                    logger.warning("Audio conversion failed, using original file")
            except Exception as e:
                logger.error(f"Audio conversion failed: {e}")
                # Fallback: use original file
                result.audio_path = input_path
                result.audio_size_bytes = result.original_size_bytes
                if result.error is None:
                    result.error = f"Audio conversion failed: {str(e)}"

            if progress_callback:
                progress_callback("completed", 100)

            logger.info(f"Audio processing completed for {video_id}")
            return result

        except Exception as e:
            logger.error(f"Audio processing failed for {video_id}: {e}")
            result.error = str(e)
            return result

    def _compress_video_task(
        self, input_path: Path, output_path: Path, config: MediaProcessingConfig
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
                preset=config.preset,
            )
            return output_path
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return None

    def _extract_audio_task(self, input_path: Path, output_path: Path, config: MediaProcessingConfig) -> Optional[Path]:
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
                audio_bitrate=config.audio_bitrate,
            )
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return None
