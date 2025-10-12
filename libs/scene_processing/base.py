"""
Base abstract class for scene processors.
Defines the interface that both sequential and parallel implementations must follow.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path


class SceneProcessor(ABC):
    """Abstract base class for scene processing implementations."""

    def __init__(self, db, storage, analyzer, temp_dir: Path):
        """
        Initialize the scene processor.

        Args:
            db: Database client
            storage: Storage client
            analyzer: Scene analyzer (Gemini)
            temp_dir: Temporary directory for file operations
        """
        self.db = db
        self.storage = storage
        self.analyzer = analyzer
        self.temp_dir = temp_dir

    @abstractmethod
    def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
        job_id: str,
        video_id: str,
        prompt_text: str,
        prompt_type: str = "scene_analysis"
    ) -> None:
        """
        Process video chunks with scene analysis.

        Args:
            chunks: List of chunk metadata dictionaries
            job_id: Scene job ID for progress tracking
            video_id: Video ID
            prompt_text: Analysis prompt text
            prompt_type: Type of analysis (scene_analysis, subtitling, etc.)

        Raises:
            Exception: If processing fails
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get processor information (CPU count, thread count, mode, etc.).

        Returns:
            Dictionary with processor info
        """
        pass
