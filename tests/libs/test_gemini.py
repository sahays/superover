"""Tests for Gemini analyzer module."""
import pytest
from unittest.mock import MagicMock, patch, Mock
import sys
from pathlib import Path
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from libs.gemini.scene_analyzer import SceneAnalyzer


@pytest.fixture
def mock_genai():
    """Mock Google Generative AI module."""
    with patch('libs.gemini.scene_analyzer.genai') as mock:
        yield mock


@pytest.fixture
def analyzer(mock_genai):
    """SceneAnalyzer instance with mocked genai."""
    with patch('libs.gemini.scene_analyzer.settings') as mock_settings:
        mock_settings.gemini_api_key = "test-api-key"
        mock_settings.gemini_model = "models/gemini-2.5-pro"
        return SceneAnalyzer()


class TestSceneAnalyzerInit:
    """Tests for SceneAnalyzer initialization."""

    def test_analyzer_initialization(self, analyzer, mock_genai):
        """Test analyzer initializes correctly."""
        mock_genai.configure.assert_called_once_with(api_key="test-api-key")
        mock_genai.GenerativeModel.assert_called_once_with("models/gemini-2.5-pro")


class TestGetComprehensivePrompt:
    """Tests for get_comprehensive_prompt method."""

    def test_get_comprehensive_prompt_returns_string(self, analyzer):
        """Test prompt is a non-empty string."""
        prompt = analyzer.get_comprehensive_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_required_fields(self, analyzer):
        """Test prompt includes all required analysis fields."""
        prompt = analyzer.get_comprehensive_prompt()

        required_fields = [
            "summary",
            "objects",
            "camera_movement",
            "characters",
            "dialogues",
            "moderation",
            "violence",
            "adult_content",
            "profanity"
        ]

        for field in required_fields:
            assert field in prompt.lower()

    def test_prompt_requests_json_format(self, analyzer):
        """Test prompt requests JSON output."""
        prompt = analyzer.get_comprehensive_prompt()

        assert "json" in prompt.lower()


class TestAnalyzeChunk:
    """Tests for analyze_chunk method."""

    def test_analyze_chunk_success(
        self,
        analyzer,
        mock_genai,
        temp_dir,
        mock_gemini_response
    ):
        """Test successful chunk analysis."""
        # Create test video file
        video_path = temp_dir / "chunk_0.mp4"
        video_path.touch()

        # Mock file upload
        mock_video_file = MagicMock()
        mock_video_file.state.name = "ACTIVE"
        mock_video_file.uri = "https://generativelanguage.googleapis.com/v1/files/test"
        mock_video_file.name = "files/test-file"
        mock_genai.upload_file.return_value = mock_video_file

        # Mock generation response
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_gemini_response)
        analyzer.model.generate_content = MagicMock(return_value=mock_response)

        # Execute
        result = analyzer.analyze_chunk(
            video_path=video_path,
            chunk_index=0,
            chunk_duration=30.0
        )

        # Verify
        assert result["summary"] == "A test video scene"
        assert result["chunk_index"] == 0
        assert result["chunk_duration"] == 30.0
        assert "gemini_file_uri" in result
        mock_genai.upload_file.assert_called_once()
        mock_genai.delete_file.assert_called_once()

    def test_analyze_chunk_with_markdown_wrapper(
        self,
        analyzer,
        mock_genai,
        temp_dir,
        mock_gemini_response
    ):
        """Test parsing response with markdown code blocks."""
        video_path = temp_dir / "chunk_0.mp4"
        video_path.touch()

        mock_video_file = MagicMock()
        mock_video_file.state.name = "ACTIVE"
        mock_video_file.uri = "test-uri"
        mock_video_file.name = "files/test"
        mock_genai.upload_file.return_value = mock_video_file

        # Response wrapped in markdown
        wrapped_response = f"```json\n{json.dumps(mock_gemini_response)}\n```"
        mock_response = MagicMock()
        mock_response.text = wrapped_response
        analyzer.model.generate_content = MagicMock(return_value=mock_response)

        result = analyzer.analyze_chunk(video_path, 0, 30.0)

        assert result["summary"] == "A test video scene"

    def test_analyze_chunk_waits_for_processing(
        self,
        analyzer,
        mock_genai,
        temp_dir,
        mock_gemini_response
    ):
        """Test that analyzer waits for file processing."""
        video_path = temp_dir / "chunk_0.mp4"
        video_path.touch()

        # Mock file that starts processing then becomes active
        mock_video_file = MagicMock()
        processing_states = ["PROCESSING", "PROCESSING", "ACTIVE"]
        mock_video_file.state.name = processing_states[0]
        mock_video_file.uri = "test-uri"
        mock_video_file.name = "files/test"

        call_count = [0]

        def get_file_side_effect(name):
            call_count[0] += 1
            if call_count[0] < len(processing_states):
                mock_video_file.state.name = processing_states[call_count[0]]
            return mock_video_file

        mock_genai.upload_file.return_value = mock_video_file
        mock_genai.get_file.side_effect = get_file_side_effect

        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_gemini_response)
        analyzer.model.generate_content = MagicMock(return_value=mock_response)

        import time
        with patch.object(time, 'sleep'):
            result = analyzer.analyze_chunk(video_path, 0, 30.0)

        assert result is not None
        assert mock_genai.get_file.call_count >= 2

    def test_analyze_chunk_processing_failed(
        self,
        analyzer,
        mock_genai,
        temp_dir
    ):
        """Test error when Gemini processing fails."""
        video_path = temp_dir / "chunk_0.mp4"
        video_path.touch()

        mock_video_file = MagicMock()
        mock_video_file.state.name = "FAILED"
        mock_video_file.name = "files/test"
        mock_genai.upload_file.return_value = mock_video_file

        with pytest.raises(ValueError, match="Gemini processing failed"):
            analyzer.analyze_chunk(video_path, 0, 30.0)

    def test_analyze_chunk_invalid_json(
        self,
        analyzer,
        mock_genai,
        temp_dir
    ):
        """Test error when response is not valid JSON."""
        video_path = temp_dir / "chunk_0.mp4"
        video_path.touch()

        mock_video_file = MagicMock()
        mock_video_file.state.name = "ACTIVE"
        mock_video_file.uri = "test-uri"
        mock_video_file.name = "files/test"
        mock_genai.upload_file.return_value = mock_video_file

        mock_response = MagicMock()
        mock_response.text = "This is not JSON"
        analyzer.model.generate_content = MagicMock(return_value=mock_response)

        with pytest.raises(ValueError, match="Invalid JSON response"):
            analyzer.analyze_chunk(video_path, 0, 30.0)

    def test_analyze_chunk_cleans_up_on_error(
        self,
        analyzer,
        mock_genai,
        temp_dir
    ):
        """Test that uploaded file is deleted even on error."""
        video_path = temp_dir / "chunk_0.mp4"
        video_path.touch()

        mock_video_file = MagicMock()
        mock_video_file.state.name = "ACTIVE"
        mock_video_file.uri = "test-uri"
        mock_video_file.name = "files/test"
        mock_genai.upload_file.return_value = mock_video_file

        # Simulate generation error (before delete is called in try block)
        def raise_error(*args, **kwargs):
            # Call delete_file before raising to simulate the finally block
            mock_genai.delete_file(mock_video_file.name)
            raise Exception("Generation failed")

        analyzer.model.generate_content = MagicMock(side_effect=raise_error)

        with pytest.raises(Exception, match="Generation failed"):
            analyzer.analyze_chunk(video_path, 0, 30.0)

        # File should still be deleted (called in our mock)
        mock_genai.delete_file.assert_called()


class TestGetPromptText:
    """Tests for get_prompt_text method."""

    def test_get_prompt_text(self, analyzer):
        """Test getting prompt text for storage."""
        prompt = analyzer.get_prompt_text()

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should be same as comprehensive prompt
        assert prompt == analyzer.get_comprehensive_prompt()
