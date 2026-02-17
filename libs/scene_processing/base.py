"""
Base abstract class for scene processors.
Defines the interface that both sequential and parallel implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
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

    def load_context_text(self, context_items: List[Dict[str, Any]]) -> str:
        """
        Load and combine all context files into a single text string.
        Context files are loaded once and reused for all chunks.

        Args:
            context_items: List of context item dictionaries with gcs_path, filename, etc.

        Returns:
            Combined context text from all files
        """
        import logging
        from pathlib import Path as PathLib
        import tempfile

        logger = logging.getLogger(__name__)

        if not context_items:
            return ""

        context_parts = []
        temp_files = []

        try:
            logger.info(f"Loading {len(context_items)} context file(s)")
            for item in context_items:
                try:
                    # Download context file from GCS
                    temp_dir = PathLib(tempfile.gettempdir())
                    context_filename = item.get("filename", f"context_{item['context_id']}.txt")
                    local_context_path = temp_dir / f"context_{item['context_id']}_{context_filename}"

                    self.storage.download_file(item["gcs_path"], local_context_path)
                    temp_files.append(local_context_path)

                    # Read text content
                    with open(local_context_path, "r", encoding="utf-8") as f:
                        file_content = f.read()

                    # Add context with label
                    context_label = item.get("description") or f"Context file: {context_filename}"
                    context_parts.append(f"=== {context_label} ===\n{file_content}")

                    logger.info(f"Loaded context file: {context_filename} ({len(file_content)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to load context file {item.get('filename')}: {e}")

            return "\n\n".join(context_parts) if context_parts else ""

        finally:
            # Clean up temporary context files
            for temp_file in temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                        logger.info(f"Deleted temp context file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp context file {temp_file}: {e}")

    @abstractmethod
    def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
        job_id: str,
        video_id: str,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
        context_items: List[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Process video chunks with scene analysis.

        Args:
            chunks: List of chunk metadata dictionaries
            job_id: Scene job ID for progress tracking
            video_id: Video ID
            prompt_text: Analysis prompt text
            prompt_type: Type of analysis (scene_analysis, subtitling, etc.)
            context_items: Optional list of context items to include in analysis
            response_schema: Optional JSON schema for structured Gemini output

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
