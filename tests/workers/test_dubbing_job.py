"""Unit tests for unified_worker dubbing job processing pipeline."""

from unittest.mock import MagicMock, patch
import pytest

from libs.db.enums import DubbingJobStatus
from workers.unified_worker import UnifiedWorker


@pytest.fixture
def mock_worker():
    """Create a UnifiedWorker instance with mocked dependencies."""
    with patch("workers.unified_worker.get_db") as mock_get_db, \
         patch("workers.unified_worker.get_storage") as mock_get_storage, \
         patch("workers.unified_worker.get_transcoder_client"), \
         patch("workers.unified_worker.get_dubbing_engine") as mock_dubbing_engine:

        db = MagicMock()
        storage = MagicMock()
        dubbing_engine = MagicMock()

        mock_get_db.return_value = db
        mock_get_storage.return_value = storage
        mock_dubbing_engine.return_value = dubbing_engine

        worker = UnifiedWorker()
        worker.db = db
        worker.storage = storage
        worker.dubbing_engine = dubbing_engine
        return worker


def test_process_pending_dubbing_jobs_happy_path(mock_worker, tmp_path):
    """Test successful dubbing job execution with real argument signatures."""
    mock_worker.temp_dir = tmp_path
    sample_job = {
        "job_id": "dub-123",
        "video_id": "vid-456",
        "config": {
            "target_languages": ["hi-IN", "es-ES"],
            "voice": "Kore",
            "mode": "voiceover",
            "ducking_db": -18.0,
            "source_language": "auto",
        },
    }

    mock_worker.db.get_pending_dubbing_jobs.return_value = [sample_job]
    mock_worker.db.get_video.return_value = {
        "video_id": "vid-456",
        "gcs_path": "gs://test-bucket/source.mp4",
    }

    async def fake_translate(*args, **kwargs):
        return {
            "audio_bytes": b"RIFF" + b"\x00" * 100,
            "input_transcripts": ["Hello world"],
            "output_transcripts": ["Namaste"],
        }

    mock_worker.dubbing_engine.translate_speech_live = fake_translate

    mock_worker._process_pending_dubbing_jobs()

    # Verify storage download was called with both source URI and local path
    mock_worker.storage.download_file.assert_called_once()
    args, kwargs = mock_worker.storage.download_file.call_args
    assert args[0] == "gs://test-bucket/source.mp4"
    assert "source_dub-123.mp4" in args[1]

    # Verify status updates and completed status
    mock_worker.db.update_dubbing_job_status.assert_any_call("dub-123", DubbingJobStatus.COMPLETED)
    assert mock_worker.db.update_dubbing_track_result.call_count == 2


def test_process_pending_dubbing_jobs_handles_error(mock_worker):
    """Test error handling when video download fails."""
    sample_job = {
        "job_id": "dub-fail-1",
        "video_id": "vid-missing",
        "config": {"target_languages": ["hi-IN"]},
    }
    mock_worker.db.get_pending_dubbing_jobs.return_value = [sample_job]
    mock_worker.db.get_video.return_value = None

    mock_worker._process_pending_dubbing_jobs()

    mock_worker.db.update_dubbing_job_status.assert_called_with(
        "dub-fail-1",
        DubbingJobStatus.FAILED,
        error_message="Dubbing pipeline error: Source video not found: vid-missing",
    )
