"""Tests for video worker."""
import pytest
from unittest.mock import MagicMock, patch, Mock, call
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from workers.video_worker import VideoWorker
from libs.database import VideoStatus, TaskStatus


@pytest.fixture
def mock_db():
    """Mock database."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_storage():
    """Mock storage."""
    storage = MagicMock()
    return storage


@pytest.fixture
def mock_analyzer():
    """Mock Gemini analyzer."""
    analyzer = MagicMock()
    return analyzer


@pytest.fixture
def worker(mock_db, mock_storage, mock_analyzer, temp_dir):
    """Create worker instance with mocks."""
    with patch('workers.video_worker.get_db', return_value=mock_db), \
         patch('workers.video_worker.get_storage', return_value=mock_storage), \
         patch('workers.video_worker.get_scene_analyzer', return_value=mock_analyzer):

        # Mock settings object with all required attributes
        mock_settings = MagicMock()
        mock_settings.get_temp_dir.return_value = temp_dir
        mock_settings.worker_poll_interval_seconds = 5
        mock_settings.max_concurrent_tasks = 3
        mock_settings.chunk_duration_seconds = 30
        mock_settings.processed_bucket = "test-bucket"

        with patch('workers.video_worker.settings', mock_settings):
            worker = VideoWorker()
            return worker


class TestVideoWorkerInit:
    """Tests for VideoWorker initialization."""

    def test_worker_initialization(self, worker, mock_db, mock_storage, mock_analyzer, temp_dir):
        """Test worker initializes correctly."""
        assert worker.db == mock_db
        assert worker.storage == mock_storage
        assert worker.analyzer == mock_analyzer
        assert worker.temp_dir == temp_dir
        assert worker.running is False


class TestProcessPendingTasks:
    """Tests for _process_pending_tasks method."""

    def test_process_pending_tasks_no_tasks(self, worker, mock_db):
        """Test processing when no pending tasks."""
        mock_db.get_pending_tasks.return_value = []

        worker._process_pending_tasks()

        mock_db.get_pending_tasks.assert_called_once()

    def test_process_pending_tasks_with_task(self, worker, mock_db, sample_task):
        """Test processing with pending task."""
        mock_db.get_pending_tasks.return_value = [sample_task]

        with patch.object(worker, '_process_task') as mock_process:
            worker._process_pending_tasks()

            mock_process.assert_called_once_with(sample_task)

    def test_process_pending_tasks_error_handling(self, worker, mock_db, sample_task):
        """Test error handling in task processing."""
        mock_db.get_pending_tasks.return_value = [sample_task]

        with patch.object(worker, '_process_task', side_effect=Exception("Test error")):
            worker._process_pending_tasks()

            # Should update task status to failed
            mock_db.update_task_status.assert_called_once()
            args = mock_db.update_task_status.call_args[0]
            assert args[0] == sample_task["task_id"]
            assert args[1] == TaskStatus.FAILED


class TestProcessTask:
    """Tests for _process_task method."""

    def test_process_task_video_processing(self, worker, mock_db, sample_task):
        """Test processing video_processing task."""
        with patch.object(worker, '_process_video') as mock_process_video:
            worker._process_task(sample_task)

            mock_db.update_task_status.assert_called_once_with(
                sample_task["task_id"],
                TaskStatus.PROCESSING
            )
            mock_process_video.assert_called_once_with(sample_task)

    def test_process_task_unknown_type(self, worker, mock_db):
        """Test processing unknown task type."""
        task = {
            "task_id": "task-123",
            "video_id": "video-123",
            "task_type": "unknown_type"
        }

        with pytest.raises(ValueError, match="Unknown task type"):
            worker._process_task(task)


class TestProcessVideo:
    """Tests for _process_video method."""

    @patch('workers.video_worker.extract_metadata')
    @patch('workers.video_worker.extract_audio')
    @patch('workers.video_worker.compress_video')
    @patch('workers.video_worker.chunk_video')
    @patch('workers.video_worker.create_manifest')
    def test_process_video_full_workflow(
        self,
        mock_create_manifest,
        mock_chunk_video,
        mock_compress_video,
        mock_extract_audio,
        mock_extract_metadata,
        worker,
        mock_db,
        mock_storage,
        mock_analyzer,
        sample_task,
        sample_video_metadata,
        temp_dir,
        mock_gemini_response
    ):
        """Test full video processing workflow."""
        # Setup mocks
        mock_db.get_video.return_value = sample_video_metadata
        mock_extract_metadata.return_value = {
            "duration": 60.0,
            "width": 1920,
            "height": 1080,
            "fps": 30.0
        }
        mock_extract_audio.return_value = temp_dir / "audio.mp3"
        mock_chunk_video.return_value = [
            {
                "index": 0,
                "filename": "chunk_0.mp4",
                "path": str(temp_dir / "chunk_0.mp4"),
                "start_time": 0.0,
                "end_time": 30.0,
                "duration": 30.0
            },
            {
                "index": 1,
                "filename": "chunk_1.mp4",
                "path": str(temp_dir / "chunk_1.mp4"),
                "start_time": 30.0,
                "end_time": 60.0,
                "duration": 30.0
            }
        ]
        mock_create_manifest.return_value = {"video_id": sample_task["video_id"]}
        mock_analyzer.get_prompt_text.return_value = "Analyze this video..."
        mock_analyzer.analyze_chunk.return_value = mock_gemini_response
        mock_db.save_prompt.return_value = "prompt-123"
        mock_db.save_result.return_value = "result-123"

        # Create dummy chunk files
        (temp_dir / "chunk_0.mp4").touch()
        (temp_dir / "chunk_1.mp4").touch()

        # Execute
        worker._process_video(sample_task)

        # Verify status updates
        status_calls = mock_db.update_video_status.call_args_list
        assert any(call[0][1] == VideoStatus.EXTRACTING_METADATA for call in status_calls)
        assert any(call[0][1] == VideoStatus.EXTRACTING_AUDIO for call in status_calls)
        assert any(call[0][1] == VideoStatus.COMPRESSING for call in status_calls)
        assert any(call[0][1] == VideoStatus.CHUNKING for call in status_calls)
        assert any(call[0][1] == VideoStatus.ANALYZING for call in status_calls)
        assert any(call[0][1] == VideoStatus.COMPLETED for call in status_calls)

        # Verify metadata and audio info saved
        mock_db.update_video_metadata.assert_called_once()
        mock_db.update_video_audio_info.assert_called_once()

        # Verify chunks analyzed
        assert mock_analyzer.analyze_chunk.call_count == 2
        assert mock_db.save_prompt.call_count == 2
        assert mock_db.save_result.call_count == 2

        # Verify manifest was created with correct parameters
        mock_create_manifest.assert_called_once()
        manifest_call = mock_create_manifest.call_args
        assert manifest_call[1]["video_id"] == sample_task["video_id"]
        assert manifest_call[1]["original_metadata"] == mock_extract_metadata.return_value
        assert "compressed_path" in manifest_call[1]
        assert "audio_path" in manifest_call[1]
        assert "chunks" in manifest_call[1]

        # Verify task completed
        mock_db.update_task_status.assert_called()
        final_call = mock_db.update_task_status.call_args_list[-1]
        assert final_call[0][1] == TaskStatus.COMPLETED

    @patch('workers.video_worker.extract_metadata')
    @patch('workers.video_worker.extract_audio')
    def test_process_video_no_audio(
        self,
        mock_extract_audio,
        mock_extract_metadata,
        worker,
        mock_db,
        mock_storage,
        sample_task,
        sample_video_metadata,
        temp_dir
    ):
        """Test video processing when video has no audio."""
        mock_db.get_video.return_value = sample_video_metadata
        mock_extract_metadata.return_value = {"duration": 60.0}
        mock_extract_audio.return_value = None  # No audio

        with patch('workers.video_worker.compress_video'), \
             patch('workers.video_worker.chunk_video', return_value=[]), \
             patch('workers.video_worker.create_manifest', return_value={}):
            worker._process_video(sample_task)

            # Verify audio info saved with has_audio=False
            audio_info_call = mock_db.update_video_audio_info.call_args[0]
            assert audio_info_call[1]["has_audio"] is False

    def test_process_video_not_found(self, worker, mock_db, sample_task):
        """Test processing when video not found."""
        mock_db.get_video.return_value = None

        with pytest.raises(ValueError, match="Video not found"):
            worker._process_video(sample_task)

    @patch('workers.video_worker.extract_metadata')
    def test_process_video_error_handling(
        self,
        mock_extract_metadata,
        worker,
        mock_db,
        mock_storage,
        sample_task,
        sample_video_metadata
    ):
        """Test error handling during video processing."""
        mock_db.get_video.return_value = sample_video_metadata
        mock_extract_metadata.side_effect = Exception("Metadata extraction failed")

        with pytest.raises(Exception, match="Metadata extraction failed"):
            worker._process_video(sample_task)

        # Verify cleanup happens (temp files deleted)
        # This is tested by the finally block


class TestAnalyzeChunks:
    """Tests for chunk analysis in workflow."""

    @patch('workers.video_worker.extract_metadata')
    @patch('workers.video_worker.extract_audio')
    @patch('workers.video_worker.compress_video')
    @patch('workers.video_worker.chunk_video')
    @patch('workers.video_worker.create_manifest')
    def test_analyze_chunks_saves_prompts_and_results(
        self,
        mock_create_manifest,
        mock_chunk_video,
        mock_compress_video,
        mock_extract_audio,
        mock_extract_metadata,
        worker,
        mock_db,
        mock_storage,
        mock_analyzer,
        sample_task,
        sample_video_metadata,
        temp_dir,
        mock_gemini_response
    ):
        """Test that prompts and results are saved for each chunk."""
        # Setup
        mock_db.get_video.return_value = sample_video_metadata
        mock_extract_metadata.return_value = {"duration": 60.0}
        mock_extract_audio.return_value = None

        chunks = [
            {
                "index": 0,
                "filename": "chunk_0.mp4",
                "path": str(temp_dir / "chunk_0.mp4"),
                "duration": 30.0,
                "gcs_path": "gs://bucket/chunk_0.mp4"
            }
        ]
        mock_chunk_video.return_value = chunks
        mock_create_manifest.return_value = {}

        prompt_text = "Analyze this video..."
        mock_analyzer.get_prompt_text.return_value = prompt_text
        mock_analyzer.analyze_chunk.return_value = mock_gemini_response

        # Create chunk file
        (temp_dir / "chunk_0.mp4").touch()

        # Execute
        worker._process_video(sample_task)

        # Verify prompt saved
        mock_db.save_prompt.assert_called_once_with(
            video_id=sample_task["video_id"],
            chunk_index=0,
            prompt_text=prompt_text,
            prompt_type="scene_analysis"
        )

        # Verify result saved
        mock_db.save_result.assert_called_once()
        result_call = mock_db.save_result.call_args
        assert result_call[1]["video_id"] == sample_task["video_id"]
        assert result_call[1]["result_type"] == "scene_analysis"
        assert result_call[1]["result_data"] == mock_gemini_response


class TestWorkerLifecycle:
    """Tests for worker start/stop."""

    def test_worker_start_stop(self, worker):
        """Test worker start and stop."""
        assert worker.running is False

        worker.stop()

        assert worker.running is False
