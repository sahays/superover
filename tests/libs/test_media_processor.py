"""Tests for media processor library."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from libs.media_processor import MediaProcessor, MediaProcessingConfig, MediaProcessingResult


class TestMediaProcessingConfig:
    """Test MediaProcessingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MediaProcessingConfig()
        assert config.compress is True
        assert config.compress_resolution == "480p"
        assert config.extract_audio is True
        assert config.audio_format == "mp3"
        assert config.audio_bitrate == "128k"
        assert config.crf == 23
        assert config.preset == "medium"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MediaProcessingConfig(
            compress=False,
            compress_resolution="1080p",
            extract_audio=False,
            audio_format="aac",
            audio_bitrate="256k",
            crf=18,
            preset="slow"
        )
        assert config.compress is False
        assert config.compress_resolution == "1080p"
        assert config.extract_audio is False
        assert config.audio_format == "aac"
        assert config.audio_bitrate == "256k"
        assert config.crf == 18
        assert config.preset == "slow"


class TestMediaProcessor:
    """Test MediaProcessor class."""

    @pytest.fixture
    def processor(self, temp_dir):
        """Create a MediaProcessor instance."""
        return MediaProcessor(temp_dir)

    @pytest.fixture
    def mock_video_path(self, temp_dir):
        """Create a mock video file."""
        video_path = temp_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video data")
        return video_path

    def test_processor_initialization(self, processor, temp_dir):
        """Test processor initializes correctly."""
        assert processor.temp_dir == temp_dir
        assert temp_dir.exists()

    @patch('libs.media_processor.processor.extract_metadata')
    @patch('libs.media_processor.processor.compress_video')
    @patch('libs.media_processor.processor.extract_audio')
    def test_process_with_all_options(
        self,
        mock_extract_audio,
        mock_compress_video,
        mock_extract_metadata,
        processor,
        mock_video_path,
        temp_dir
    ):
        """Test processing with all options enabled."""
        # Setup mocks
        mock_extract_metadata.return_value = {
            "duration": 60.0,
            "format": "mp4",
            "video": {"width": 1920, "height": 1080}
        }

        # Mock compress_video to create file at the provided output path
        # Make compressed file smaller to get a valid compression ratio
        def mock_compress_side_effect(input_path, output_path, **kwargs):
            output_path.write_bytes(b"compressed")  # 10 bytes vs original 15 bytes

        mock_compress_video.side_effect = mock_compress_side_effect

        # Mock extract_audio to create file at the provided output path
        def mock_audio_side_effect(input_path, output_path, **kwargs):
            output_path.write_bytes(b"audio data")
            return output_path

        mock_extract_audio.side_effect = mock_audio_side_effect

        # Execute
        config = MediaProcessingConfig(
            compress=True,
            extract_audio=True
        )
        result = processor.process(
            input_path=mock_video_path,
            video_id="test-123",
            config=config
        )

        # Verify
        assert result.metadata is not None
        assert result.compressed_video_path is not None
        assert result.compressed_video_path.name == "test-123_compressed.mp4"
        assert result.compressed_video_path.exists()
        assert result.audio_path is not None
        assert result.audio_path.name == "test-123_audio.mp3"
        assert result.audio_path.exists()
        assert result.error is None
        assert result.original_size_bytes > 0
        assert result.compressed_size_bytes > 0
        assert result.compression_ratio > 0

        mock_extract_metadata.assert_called_once_with(mock_video_path)
        mock_compress_video.assert_called_once()
        mock_extract_audio.assert_called_once()

    @patch('libs.media_processor.processor.extract_metadata')
    def test_process_metadata_only(
        self,
        mock_extract_metadata,
        processor,
        mock_video_path
    ):
        """Test processing with only metadata extraction."""
        mock_extract_metadata.return_value = {
            "duration": 30.0,
            "format": "mp4"
        }

        config = MediaProcessingConfig(
            compress=False,
            extract_audio=False
        )
        result = processor.process(
            input_path=mock_video_path,
            video_id="test-456",
            config=config
        )

        assert result.metadata is not None
        assert result.compressed_video_path is None
        assert result.audio_path is None
        assert result.error is None
        mock_extract_metadata.assert_called_once()

    @patch('libs.media_processor.processor.extract_metadata')
    def test_process_with_error(
        self,
        mock_extract_metadata,
        processor,
        mock_video_path
    ):
        """Test processing handles errors gracefully."""
        mock_extract_metadata.side_effect = Exception("Test error")

        config = MediaProcessingConfig()
        result = processor.process(
            input_path=mock_video_path,
            video_id="test-789",
            config=config
        )

        assert result.error == "Test error"
        assert result.metadata == {}

    @patch('libs.media_processor.processor.extract_metadata')
    @patch('libs.media_processor.processor.compress_video')
    @patch('libs.media_processor.processor.extract_audio')
    def test_process_with_progress_callback(
        self,
        mock_extract_audio,
        mock_compress_video,
        mock_extract_metadata,
        processor,
        mock_video_path,
        temp_dir
    ):
        """Test progress callback is called during processing."""
        mock_extract_metadata.return_value = {"duration": 60.0}

        # Mock compress_video to create file at the provided output path
        def mock_compress_side_effect(input_path, output_path, **kwargs):
            output_path.write_bytes(b"compressed")

        mock_compress_video.side_effect = mock_compress_side_effect

        # Mock extract_audio to create file at the provided output path
        def mock_audio_side_effect(input_path, output_path, **kwargs):
            output_path.write_bytes(b"audio")
            return output_path

        mock_extract_audio.side_effect = mock_audio_side_effect

        progress_calls = []
        def progress_callback(step, percent):
            progress_calls.append((step, percent))

        config = MediaProcessingConfig()
        result = processor.process(
            input_path=mock_video_path,
            video_id="test-progress",
            config=config,
            progress_callback=progress_callback
        )

        # Verify progress callback was called
        assert len(progress_calls) > 0
        assert ("extracting_metadata", 10) in progress_calls
        assert ("completed", 100) in progress_calls

    @patch('libs.media_processor.processor.extract_metadata')
    @patch('libs.media_processor.processor.compress_video')
    def test_compression_ratio_calculation(
        self,
        mock_compress_video,
        mock_extract_metadata,
        processor,
        mock_video_path,
        temp_dir
    ):
        """Test compression ratio is calculated correctly."""
        mock_extract_metadata.return_value = {"duration": 60.0}

        # Original file: 1000 bytes
        mock_video_path.write_bytes(b"x" * 1000)

        # Mock compress_video to create compressed file: 500 bytes (50% reduction)
        def mock_compress_side_effect(input_path, output_path, **kwargs):
            output_path.write_bytes(b"x" * 500)

        mock_compress_video.side_effect = mock_compress_side_effect

        config = MediaProcessingConfig(
            compress=True,
            extract_audio=False
        )
        result = processor.process(
            input_path=mock_video_path,
            video_id="test-ratio",
            config=config
        )

        assert result.original_size_bytes == 1000
        assert result.compressed_size_bytes == 500
        assert result.compression_ratio == 50.0


class TestMediaProcessorIntegration:
    """Integration tests for MediaProcessor (require ffmpeg)."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        not Path("/usr/bin/ffmpeg").exists() and not Path("/usr/local/bin/ffmpeg").exists(),
        reason="ffmpeg not installed"
    )
    def test_real_video_processing(self, temp_dir, sample_video_file):
        """Test processing a real video file (requires ffmpeg)."""
        processor = MediaProcessor(temp_dir)

        config = MediaProcessingConfig(
            compress=True,
            compress_resolution="360p",
            extract_audio=True
        )

        # Note: sample_video_file is just a header, so this will fail
        # In a real test, you'd use a proper video file
        with pytest.raises(Exception):
            result = processor.process(
                input_path=sample_video_file,
                video_id="integration-test",
                config=config
            )
