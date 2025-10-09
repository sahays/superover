"""Tests for database module."""
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from libs.database import FirestoreDB, VideoStatus, TaskStatus


@pytest.fixture
def db():
    """FirestoreDB instance with mocked client."""
    with patch('libs.database.firestore.Client') as mock_client:
        with patch('libs.database.settings') as mock_settings:
            mock_settings.gcp_project_id = "test-project"
            mock_settings.firestore_database = "(default)"

            # Create FirestoreDB instance
            db_instance = FirestoreDB()

            # Replace collections with mocks
            db_instance.videos = MagicMock()
            db_instance.scene_tasks = MagicMock()
            db_instance.scene_results = MagicMock()
            db_instance.scene_prompts = MagicMock()
            db_instance.scene_manifests = MagicMock()
            db_instance.scene_jobs = MagicMock()
            db_instance.media_jobs = MagicMock()

            yield db_instance


class TestVideoOperations:
    """Tests for video database operations."""

    def test_create_video(self, db):
        """Test creating a video document."""
        mock_doc = MagicMock()
        db.videos.document.return_value = mock_doc

        # Mock get_video to return the created video
        with patch.object(db, 'get_video', return_value={"video_id": "test-123"}):
            result = db.create_video(
                video_id="test-123",
                filename="test.mp4",
                gcs_path="gs://bucket/test.mp4",
                content_type="video/mp4",
                size_bytes=1024000
            )

            assert result["video_id"] == "test-123"
            mock_doc.set.assert_called_once()

    def test_get_video(self, db):
        """Test getting a video document."""
        mock_doc_ref = MagicMock()
        db.videos.document.return_value = mock_doc_ref

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"video_id": "test-123"}
        mock_doc_ref.get.return_value = mock_doc

        result = db.get_video("test-123")

        assert result["video_id"] == "test-123"

    def test_get_video_not_found(self, db):
        """Test getting non-existent video."""
        mock_doc_ref = MagicMock()
        db.videos.document.return_value = mock_doc_ref

        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc

        result = db.get_video("nonexistent")

        assert result is None

    def test_update_video_status(self, db):
        """Test updating video status."""
        mock_doc = MagicMock()
        db.videos.document.return_value = mock_doc

        db.update_video_status("test-123", VideoStatus.ANALYZING)

        mock_doc.update.assert_called_once()
        update_data = mock_doc.update.call_args[0][0]
        assert update_data["status"] == VideoStatus.ANALYZING

    def test_update_video_metadata(self, db):
        """Test updating video metadata."""
        mock_doc = MagicMock()
        db.videos.document.return_value = mock_doc

        metadata = {"duration": 60.0, "width": 1920, "height": 1080}
        db.update_video_metadata("test-123", metadata)

        mock_doc.update.assert_called_once()
        update_data = mock_doc.update.call_args[0][0]
        assert update_data["metadata"] == metadata

    def test_update_video_audio_info(self, db):
        """Test updating video audio info."""
        mock_doc = MagicMock()
        db.videos.document.return_value = mock_doc

        audio_info = {"has_audio": True, "gcs_path": "gs://bucket/audio.mp3"}
        db.update_video_audio_info("test-123", audio_info)

        mock_doc.update.assert_called_once()
        update_data = mock_doc.update.call_args[0][0]
        assert update_data["audio_info"] == audio_info

    def test_list_videos(self, db):
        """Test listing videos."""
        mock_query = MagicMock()
        db.videos.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query

        mock_docs = [
            MagicMock(to_dict=lambda: {"video_id": "1"}),
            MagicMock(to_dict=lambda: {"video_id": "2"})
        ]
        mock_query.stream.return_value = mock_docs

        results = db.list_videos()

        assert len(results) == 2
        assert results[0]["video_id"] == "1"


class TestTaskOperations:
    """Tests for task database operations."""

    def test_create_task(self, db):
        """Test creating a scene task."""
        mock_doc = MagicMock()
        db.scene_tasks.document.return_value = mock_doc

        result = db.create_task(
            task_id="task-123",
            video_id="video-123",
            task_type="video_processing",
            input_data={"compress": True}
        )

        assert result["task_id"] == "task-123"
        mock_doc.set.assert_called_once()

    def test_update_task_status(self, db):
        """Test updating scene task status."""
        mock_doc = MagicMock()
        db.scene_tasks.document.return_value = mock_doc

        db.update_task_status(
            "task-123",
            TaskStatus.COMPLETED,
            result_data={"success": True}
        )

        mock_doc.update.assert_called_once()
        update_data = mock_doc.update.call_args[0][0]
        assert update_data["status"] == TaskStatus.COMPLETED
        assert update_data["result_data"] == {"success": True}

    def test_get_pending_tasks(self, db):
        """Test getting pending scene tasks."""
        mock_query = MagicMock()
        db.scene_tasks.where.return_value = mock_query
        mock_query.limit.return_value = mock_query

        mock_docs = [
            MagicMock(to_dict=lambda: {"task_id": "1", "created_at": 1}),
            MagicMock(to_dict=lambda: {"task_id": "2", "created_at": 2})
        ]
        mock_query.stream.return_value = mock_docs

        results = db.get_pending_tasks()

        assert len(results) == 2


class TestResultOperations:
    """Tests for result database operations."""

    def test_save_result(self, db):
        """Test saving scene analysis result."""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "result-123"
        db.scene_results.add.return_value = (None, mock_doc_ref)

        result_id = db.save_result(
            video_id="video-123",
            result_type="scene_analysis",
            result_data={"summary": "Test"}
        )

        assert result_id == "result-123"
        db.scene_results.add.assert_called_once()

    def test_get_results_for_video(self, db):
        """Test getting scene results for a video."""
        mock_query = MagicMock()
        db.scene_results.where.return_value = mock_query

        mock_docs = [
            MagicMock(to_dict=lambda: {"result_type": "scene_analysis"})
        ]
        mock_query.stream.return_value = mock_docs

        results = db.get_results_for_video("video-123")

        assert len(results) == 1


class TestPromptOperations:
    """Tests for prompt database operations."""

    def test_save_prompt(self, db):
        """Test saving a scene prompt."""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "prompt-123"
        db.scene_prompts.add.return_value = (None, mock_doc_ref)

        prompt_id = db.save_prompt(
            video_id="video-123",
            chunk_index=0,
            prompt_text="Analyze this video...",
            prompt_type="scene_analysis"
        )

        assert prompt_id == "prompt-123"
        db.scene_prompts.add.assert_called_once()
