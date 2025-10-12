"""
Sequential Scene Processor
Processes video chunks one at a time (current implementation).
Exact copy of existing logic - ensures zero regression.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any
from google.api_core import exceptions as google_exceptions
from libs.database import SceneJobStatus
from .base import SceneProcessor

logger = logging.getLogger(__name__)


class SequentialSceneProcessor(SceneProcessor):
    """Processes scene chunks sequentially (one at a time)."""

    def get_info(self) -> Dict[str, Any]:
        """Get processor information."""
        return {
            "mode": "sequential",
            "cpu_count": 1,
            "thread_count": 1,
            "description": "Sequential single-threaded processing"
        }

    def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
        job_id: str,
        video_id: str,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
        context_items: List[Dict[str, Any]] = None
    ) -> None:
        """
        Process video chunks sequentially.

        Args:
            chunks: List of chunk metadata dictionaries
            job_id: Scene job ID for progress tracking
            video_id: Video ID
            prompt_text: Analysis prompt text
            prompt_type: Type of analysis (scene_analysis, subtitling, etc.)
            context_items: Optional list of context items to include in analysis

        Raises:
            Exception: If processing fails
        """
        logger.info(f"[SEQUENTIAL] Analyzing {len(chunks)} chunk(s) for job {job_id}")

        # Load context files once (not per chunk)
        context_text = self.load_context_text(context_items) if context_items else None
        if context_text:
            logger.info(f"[SEQUENTIAL] Loaded context text ({len(context_text)} chars) - will be reused for all chunks")

        for chunk in chunks:
            chunk_index = chunk["index"]
            chunk_gcs = chunk["gcs_path"]

            logger.info(f"Analyzing chunk {chunk_index + 1}/{len(chunks)}")

            # Update progress
            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.PROCESSING,
                results={
                    "step": "analyzing",
                    "progress": {
                        "completed_chunks": chunk_index,
                        "total_chunks": len(chunks)
                    }
                }
            )

            # Use local_path if available (no-chunking case), otherwise download from GCS
            if "local_path" in chunk:
                local_chunk_path = Path(chunk["local_path"])
                logger.info(f"Using already-downloaded video file: {local_chunk_path}")
            else:
                # Download chunk from GCS
                local_chunk_path = self.temp_dir / f"{video_id}_{chunk['filename']}"
                self.storage.download_file(chunk_gcs, local_chunk_path)

            try:
                # Analyze with Gemini (context already loaded and passed as text)
                result = self.analyzer.analyze_chunk(
                    video_path=local_chunk_path,
                    chunk_index=chunk_index,
                    chunk_duration=chunk["duration"],
                    prompt_text=prompt_text,
                    prompt_type=prompt_type,
                    context_text=context_text,
                )

                # Save result to database
                result_id = self.db.save_result(
                    video_id=video_id,
                    result_type="scene_analysis",
                    result_data=result,
                    scene_job_id=job_id
                )
                logger.info(f"Saved analysis result {result_id} for chunk {chunk_index}")

                # Update progress after successful scene analysis
                self.db.update_scene_job_status(
                    job_id,
                    SceneJobStatus.PROCESSING,
                    results={
                        "step": "analyzing",
                        "progress": {
                            "completed_chunks": chunk_index + 1,
                            "total_chunks": len(chunks)
                        }
                    }
                )

            except google_exceptions.DeadlineExceeded as e:
                error_msg = (
                    f"Gemini API timeout for chunk {chunk_index + 1}/{len(chunks)}. "
                    f"The video chunk may be too large or complex. "
                    f"Consider using shorter chunk durations (e.g., 15-30 seconds). "
                    f"Error: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg) from e

            except google_exceptions.ServiceUnavailable as e:
                error_msg = (
                    f"Gemini API service unavailable for chunk {chunk_index + 1}/{len(chunks)}. "
                    f"This is usually a temporary issue. Please try again later. "
                    f"Error: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg) from e

            finally:
                # Clean up chunk file (but not if it's the original downloaded file)
                if "local_path" not in chunk and local_chunk_path.exists():
                    local_chunk_path.unlink()

        logger.info(f"[SEQUENTIAL] Completed all {len(chunks)} chunks for job {job_id}")
