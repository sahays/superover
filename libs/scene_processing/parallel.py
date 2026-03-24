"""
Parallel Scene Processor
Analyzes chunks in parallel using multiple processes.
Chunks are in GCS — Gemini reads them directly via GCS URI (no local download).
"""

import logging
import multiprocessing
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from google.api_core import exceptions as google_exceptions
from libs.database import SceneJobStatus
from .base import SceneProcessor

logger = logging.getLogger(__name__)


# Global worker function - must be at module level for pickling
def _analyze_chunk_worker(chunk_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker function for analyzing a single chunk with Gemini in a separate process.
    Gemini reads the chunk directly from GCS — no local file needed.

    Args:
        chunk_data: Dictionary containing chunk info and GCS path

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
    import logging

    # Configure logging for this process
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [Process-%(process)d] - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Extract data
    chunk_index = chunk_data["chunk_index"]
    chunk_duration = chunk_data["chunk_duration"]
    chunk_gcs_path = chunk_data["gcs_path"]
    prompt_text = chunk_data["prompt_text"]
    prompt_type = chunk_data.get("prompt_type", "scene_analysis")
    context_text = chunk_data.get("context_text")
    response_schema = chunk_data.get("response_schema")
    use_chirp = chunk_data.get("use_chirp", False)
    job_id = chunk_data["job_id"]
    video_id = chunk_data["video_id"]
    total_chunks = chunk_data["total_chunks"]
    process_id = multiprocessing.current_process().pid

    # Initialize clients in THIS process (isolated SSL context)
    db = get_db()
    analyzer = get_scene_analyzer()

    logger.info(f"[Process-{process_id}] Analyzing chunk {chunk_index + 1}/{total_chunks} from {chunk_gcs_path}")

    try:
        # Chirp 3 pre-processing for subtitle jobs
        chunk_context = context_text or ""
        chirp_metadata = None
        if use_chirp:
            from libs.speech import get_speech_client

            speech_client = get_speech_client()
            chirp_input = chunk_data.get("chirp_audio_gcs") or chunk_gcs_path
            chirp_result = speech_client.transcribe_gcs(chirp_input)
            chirp_text = speech_client.format_as_context(chirp_result)
            if not chirp_text:
                raise ValueError(
                    f"Chirp 3 returned empty transcription for chunk {chunk_index}. "
                    f"Ensure an extracted audio file is available (not raw video)."
                )
            chunk_context = chirp_text + ("\n\n" + chunk_context if chunk_context else "")
            chirp_metadata = {
                "utterance_count": len(chirp_result.get("utterances", [])),
                "detected_language": chirp_result.get("detected_language", ""),
                "timestamps": chirp_text,
            }
            logger.info(
                f"[Process-{process_id}] Chirp 3 for chunk {chunk_index}: {chirp_result.get('word_count', 0)} words"
            )

        # Analyze with Gemini — GCS URI passed directly, no local file
        result = analyzer.analyze_chunk(
            media_path=None,
            chunk_index=chunk_index,
            chunk_duration=chunk_duration,
            prompt_text=prompt_text,
            prompt_type=prompt_type,
            context_text=chunk_context or None,
            gcs_path=chunk_gcs_path,
            response_schema=response_schema,
        )

        if chirp_metadata:
            result["chirp_transcription"] = chirp_metadata

        # Tag result with prompt_type for filtering
        result["prompt_type"] = prompt_type

        # Save result to database
        result_id = db.save_result(
            video_id=video_id,
            result_type="scene_analysis",
            result_data=result,
            scene_job_id=job_id,
        )

        logger.info(f"[Process-{process_id}] Saved analysis result {result_id} for chunk {chunk_index}")

        return {
            "chunk_index": chunk_index,
            "result_id": result_id,
            "success": True,
            "error": None,
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
            "error": error_msg,
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
            "error": error_msg,
        }

    except Exception as e:
        error_msg = f"Unexpected error processing chunk {chunk_index}: {type(e).__name__}: {e}"
        logger.error(f"[Process-{process_id}] {error_msg}")
        return {
            "chunk_index": chunk_index,
            "result_id": None,
            "success": False,
            "error": error_msg,
        }


class ParallelSceneProcessor(SceneProcessor):
    """Processes scene chunks in parallel using multiple processes."""

    def __init__(self, db, storage, analyzer, temp_dir: Path, max_workers: int = None, speech_client=None):
        super().__init__(db, storage, analyzer, temp_dir, speech_client=speech_client)
        self.cpu_count = multiprocessing.cpu_count()

        if max_workers is None:
            self.max_workers = self.cpu_count
        else:
            self.max_workers = min(max_workers, self.cpu_count)

    def get_info(self) -> Dict[str, Any]:
        """Get processor information."""
        return {
            "mode": "parallel",
            "cpu_count": self.cpu_count,
            "max_workers": self.max_workers,
            "process_based": True,
            "description": f"Parallel Gemini analysis ({self.max_workers} processes), GCS-direct",
        }

    def _update_progress(self, job_id: str, completed: int, total: int):
        try:
            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.PROCESSING,
                results={
                    "step": "analyzing",
                    "progress": {"completed_chunks": completed, "total_chunks": total},
                },
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
        context_items: List[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Process chunks in parallel. Gemini reads chunks directly from GCS.

        Args:
            chunks: List of chunk metadata dictionaries (must have gcs_path)
            job_id: Scene job ID for progress tracking
            video_id: Video ID
            prompt_text: Analysis prompt text
            prompt_type: Type of analysis
            context_items: Optional list of context items
            response_schema: Optional JSON schema for structured Gemini output

        Raises:
            Exception: If processing fails
        """
        total_chunks = len(chunks)
        logger.info(f"[PARALLEL] Processing {total_chunks} chunks with {self.max_workers} processes, GCS-direct")

        # Load context files once
        context_text = self.load_context_text(context_items) if context_items else None
        if context_text:
            logger.info(f"[PARALLEL] Loaded context text ({len(context_text)} chars)")

        # Determine if Chirp 3 pre-processing is needed
        use_chirp = prompt_type in ("subtitling", "transcription") and self.speech_client is not None
        chirp_audio_gcs = None
        if use_chirp:
            logger.info(f"[PARALLEL] Chirp 3 enabled for prompt_type={prompt_type}")
            try:
                media_jobs = self.db.list_media_jobs_for_video(video_id)
                for mj in media_jobs:
                    if mj.get("status") == "completed" and mj.get("results", {}).get("audio_path"):
                        chirp_audio_gcs = mj["results"]["audio_path"]
                        logger.info(f"[PARALLEL] Using extracted audio for Chirp 3: {chirp_audio_gcs}")
                        break
            except Exception as e:
                logger.warning(f"[PARALLEL] Could not find extracted audio: {e}")

        # Prepare tasks — no file downloads needed
        gemini_tasks = [
            {
                "chunk_index": chunk["index"],
                "chunk_duration": chunk["duration"],
                "gcs_path": chunk["gcs_path"],
                "prompt_text": prompt_text,
                "prompt_type": prompt_type,
                "context_text": context_text,
                "response_schema": response_schema,
                "use_chirp": use_chirp,
                "chirp_audio_gcs": chirp_audio_gcs,
                "job_id": job_id,
                "video_id": video_id,
                "total_chunks": total_chunks,
            }
            for chunk in chunks
        ]

        completed_count = 0
        errors = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(_analyze_chunk_worker, task): task["chunk_index"] for task in gemini_tasks
            }

            for future in as_completed(future_to_index):
                chunk_index = future_to_index[future]

                try:
                    result = future.result()

                    if result["success"]:
                        completed_count += 1
                        self._update_progress(job_id, completed_count, total_chunks)
                        logger.info(
                            f"[PARALLEL] Progress: {completed_count}/{total_chunks} chunks analyzed "
                            f"(chunk {chunk_index}, result_id: {result['result_id']})"
                        )
                    else:
                        errors.append({"chunk_index": chunk_index, "error": result["error"]})
                        logger.error(f"[PARALLEL] Chunk {chunk_index} failed: {result['error']}")

                except Exception as e:
                    errors.append({"chunk_index": chunk_index, "error": f"Process crash: {type(e).__name__}: {e}"})
                    logger.error(f"[PARALLEL] Process for chunk {chunk_index} crashed: {e}")

        if errors:
            error_summary = f"Failed to process {len(errors)}/{total_chunks} chunks: {errors}"
            logger.error(f"[PARALLEL] {error_summary}")
            raise Exception(error_summary)

        logger.info(f"[PARALLEL] Successfully completed all {total_chunks} chunks for job {job_id}")
