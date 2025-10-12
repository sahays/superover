"""
Hybrid Parallel Scene Processor
- Sequential: File downloads and chunking (safe, predictable)
- Parallel: Gemini API calls only (isolated processes for speed and SSL safety)
"""
import logging
import multiprocessing
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
from google.api_core import exceptions as google_exceptions
from libs.database import SceneJobStatus
from .base import SceneProcessor

logger = logging.getLogger(__name__)


# Global worker function - must be at module level for pickling
def _analyze_chunk_worker(chunk_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker function for analyzing a single chunk with Gemini in a separate process.
    File is already downloaded - this only does Gemini API call.
    Runs in isolated process with its own SSL context.

    Args:
        chunk_data: Dictionary containing chunk info and local file path

    Returns:
        Result dictionary with chunk_index, result_id, and success status
    """
    import sys
    from pathlib import Path

    # Add project root to path (each process needs this)
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from libs.database import get_db
    from libs.gemini import get_scene_analyzer
    from google.api_core import exceptions as google_exceptions
    import logging

    # Configure logging for this process
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [Process-%(process)d] - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Extract data
    chunk_index = chunk_data['chunk_index']
    local_chunk_path = Path(chunk_data['local_chunk_path'])
    chunk_duration = chunk_data['chunk_duration']
    prompt_text = chunk_data['prompt_text']
    prompt_type = chunk_data.get('prompt_type', 'scene_analysis')
    context_text = chunk_data.get('context_text')  # Pre-loaded context text
    job_id = chunk_data['job_id']
    video_id = chunk_data['video_id']
    total_chunks = chunk_data['total_chunks']
    process_id = multiprocessing.current_process().pid

    # Initialize clients in THIS process (isolated SSL context)
    db = get_db()
    analyzer = get_scene_analyzer()

    logger.info(f"[Process-{process_id}] Analyzing chunk {chunk_index + 1}/{total_chunks} with Gemini")

    try:
        # Analyze with Gemini (isolated SSL context per process)
        # Context text is already loaded and passed as string
        result = analyzer.analyze_chunk(
            video_path=local_chunk_path,
            chunk_index=chunk_index,
            chunk_duration=chunk_duration,
            prompt_text=prompt_text,
            prompt_type=prompt_type,
            context_text=context_text,
        )

        # Save result to database
        result_id = db.save_result(
            video_id=video_id,
            result_type="scene_analysis",
            result_data=result,
            scene_job_id=job_id
        )

        logger.info(f"[Process-{process_id}] Saved analysis result {result_id} for chunk {chunk_index}")

        return {
            "chunk_index": chunk_index,
            "result_id": result_id,
            "success": True,
            "error": None
        }

    except google_exceptions.DeadlineExceeded as e:
        error_msg = (
            f"Gemini API timeout for chunk {chunk_index + 1}/{total_chunks}. "
            f"The video chunk may be too large or complex. "
            f"Consider using shorter chunk durations (e.g., 15-30 seconds). "
            f"Error: {e}"
        )
        logger.error(f"[Process-{process_id}] {error_msg}")
        return {
            "chunk_index": chunk_index,
            "result_id": None,
            "success": False,
            "error": error_msg
        }

    except google_exceptions.ServiceUnavailable as e:
        error_msg = (
            f"Gemini API service unavailable for chunk {chunk_index + 1}/{total_chunks}. "
            f"This is usually a temporary issue. Please try again later. "
            f"Error: {e}"
        )
        logger.error(f"[Process-{process_id}] {error_msg}")
        return {
            "chunk_index": chunk_index,
            "result_id": None,
            "success": False,
            "error": error_msg
        }

    except Exception as e:
        error_msg = f"Unexpected error processing chunk {chunk_index}: {type(e).__name__}: {e}"
        logger.error(f"[Process-{process_id}] {error_msg}")
        return {
            "chunk_index": chunk_index,
            "result_id": None,
            "success": False,
            "error": error_msg
        }


class ParallelSceneProcessor(SceneProcessor):
    """Processes scene chunks in parallel using multiple processes (memory isolated)."""

    def __init__(self, db, storage, analyzer, temp_dir: Path, max_workers: int = None):
        """
        Initialize parallel scene processor with process-based parallelism.

        Args:
            db: Database client (not used in processes, each process creates own)
            storage: Storage client (not used in processes)
            analyzer: Scene analyzer (not used in processes)
            temp_dir: Temporary directory
            max_workers: Maximum concurrent processes (defaults to CPU count)
        """
        super().__init__(db, storage, analyzer, temp_dir)
        self.cpu_count = multiprocessing.cpu_count()

        # Use CPU count as default, or user-specified value
        if max_workers is None:
            self.max_workers = self.cpu_count
        else:
            # Cap at CPU count for process-based parallelism
            self.max_workers = min(max_workers, self.cpu_count)

    def get_info(self) -> Dict[str, Any]:
        """Get processor information."""
        return {
            "mode": "parallel",
            "cpu_count": self.cpu_count,
            "max_workers": self.max_workers,
            "process_based": True,
            "description": f"Hybrid: sequential I/O, parallel Gemini ({self.max_workers} processes)"
        }

    def _update_progress(self, job_id: str, completed: int, total: int):
        """
        Update progress in database (process-safe via Firestore).

        Args:
            job_id: Scene job ID
            completed: Number of completed chunks
            total: Total number of chunks
        """
        try:
            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.PROCESSING,
                results={
                    "step": "analyzing",
                    "progress": {
                        "completed_chunks": completed,
                        "total_chunks": total
                    }
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")

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
        Hybrid processing: Sequential I/O, Parallel Gemini API calls.

        1. Download all chunk files sequentially (predictable, safe)
        2. Analyze with Gemini in parallel processes (fast, isolated SSL)
        3. Clean up files sequentially

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
        total_chunks = len(chunks)
        logger.info(
            f"[HYBRID] Processing {total_chunks} chunks: sequential I/O, parallel Gemini "
            f"({self.max_workers} processes, {self.cpu_count} CPUs)"
        )

        # STEP 1: Download all chunks SEQUENTIALLY (safe, predictable)
        logger.info(f"[HYBRID] Step 1/3: Downloading {total_chunks} chunks sequentially...")
        local_chunk_paths = []

        for i, chunk in enumerate(chunks):
            chunk_index = chunk["index"]

            # Use local_path if available (no-chunking case)
            if "local_path" in chunk:
                local_chunk_path = Path(chunk["local_path"])
                logger.info(f"[HYBRID] Chunk {i+1}/{total_chunks}: Using already-downloaded file")
            else:
                # Download chunk from GCS
                local_chunk_path = self.temp_dir / f"{video_id}_{chunk['filename']}"
                self.storage.download_file(chunk["gcs_path"], local_chunk_path)
                logger.info(f"[HYBRID] Chunk {i+1}/{total_chunks}: Downloaded from GCS")

            local_chunk_paths.append(local_chunk_path)

        # Load context files once (not per chunk, not per process)
        context_text = self.load_context_text(context_items) if context_items else None
        if context_text:
            logger.info(f"[HYBRID] Loaded context text ({len(context_text)} chars) - will be reused for all chunks")

        logger.info(f"[HYBRID] Step 2/3: Analyzing {total_chunks} chunks in parallel with Gemini...")

        # STEP 2: Analyze with Gemini in PARALLEL (isolated processes)
        completed_count = 0
        errors = []

        # Prepare tasks for parallel Gemini processing
        gemini_tasks = [
            {
                "chunk_index": chunk["index"],
                "local_chunk_path": str(local_chunk_paths[i]),
                "chunk_duration": chunk["duration"],
                "prompt_text": prompt_text,
                "prompt_type": prompt_type,
                "context_text": context_text,  # Pre-loaded context text (not items)
                "job_id": job_id,
                "video_id": video_id,
                "total_chunks": total_chunks,
            }
            for i, chunk in enumerate(chunks)
        ]

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all Gemini analysis tasks
            future_to_index = {
                executor.submit(_analyze_chunk_worker, task): task["chunk_index"]
                for task in gemini_tasks
            }

            # Process results as they complete
            for future in as_completed(future_to_index):
                chunk_index = future_to_index[future]

                try:
                    result = future.result()

                    if result["success"]:
                        completed_count += 1

                        # Update progress
                        self._update_progress(job_id, completed_count, total_chunks)

                        logger.info(
                            f"[HYBRID] Progress: {completed_count}/{total_chunks} chunks analyzed "
                            f"(chunk {chunk_index}, result_id: {result['result_id']})"
                        )
                    else:
                        # Worker reported failure
                        error_info = {
                            "chunk_index": chunk_index,
                            "error": result["error"]
                        }
                        errors.append(error_info)
                        logger.error(f"[HYBRID] Chunk {chunk_index} failed: {result['error']}")

                except Exception as e:
                    # Process itself crashed
                    error_info = {
                        "chunk_index": chunk_index,
                        "error": f"Process crash: {type(e).__name__}: {e}"
                    }
                    errors.append(error_info)
                    logger.error(f"[HYBRID] Process for chunk {chunk_index} crashed: {e}")

        # STEP 3: Clean up downloaded files SEQUENTIALLY
        logger.info(f"[HYBRID] Step 3/3: Cleaning up {total_chunks} temporary files...")
        for i, chunk in enumerate(chunks):
            # Only delete if we downloaded it (not the original file)
            if "local_path" not in chunk:
                try:
                    if local_chunk_paths[i].exists():
                        local_chunk_paths[i].unlink()
                        logger.info(f"[HYBRID] Deleted temp file: {local_chunk_paths[i].name}")
                except Exception as e:
                    logger.warning(f"[HYBRID] Failed to delete temp file {local_chunk_paths[i]}: {e}")

        # Check if we had any errors
        if errors:
            error_summary = f"Failed to process {len(errors)}/{total_chunks} chunks: {errors}"
            logger.error(f"[HYBRID] {error_summary}")
            raise Exception(error_summary)

        logger.info(f"[HYBRID] Successfully completed all {total_chunks} chunks for job {job_id}")
