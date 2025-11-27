"""
Scene Processing Worker
Polls Firestore for pending scene processing tasks and executes them.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
import time
import traceback
import uuid
from config import settings
from libs.database import get_db, SceneJobStatus
from libs.storage import get_storage
from libs.video_processing import chunk_video
from libs.gemini import get_scene_analyzer
from libs.scene_processing import get_scene_processor
from google.api_core import exceptions as google_exceptions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SceneWorker:
    """Worker for processing scene files."""

    def __init__(self):
        """Initialize worker."""
        self.db = get_db()
        self.storage = get_storage()
        self.analyzer = get_scene_analyzer()
        self.temp_dir = settings.get_temp_dir()
        self.running = False

        # Initialize scene processor (sequential or parallel based on config)
        self.scene_processor = get_scene_processor(
            db=self.db,
            storage=self.storage,
            analyzer=self.analyzer,
            temp_dir=self.temp_dir
        )

    def start(self):
        """Start the worker loop."""
        self.running = True

        # Get processor info for logging
        processor_info = self.scene_processor.get_info()

        logger.info("=" * 60)
        logger.info("Scene Processing Worker Started")
        logger.info(f"Polling interval: {settings.worker_poll_interval_seconds}s")
        logger.info(f"Max concurrent tasks: {settings.max_concurrent_tasks}")
        logger.info("-" * 60)
        logger.info("Scene Processor Configuration:")
        logger.info(f"  Mode: {processor_info['mode'].upper()}")
        logger.info(f"  CPU Count: {processor_info.get('cpu_count', 'N/A')}")
        if processor_info['mode'] == 'parallel':
            logger.info(f"  Max Workers: {processor_info.get('max_workers', 'N/A')}")
            logger.info(f"  Process-Based: {processor_info.get('process_based', 'N/A')}")
        logger.info(f"  Description: {processor_info.get('description', 'N/A')}")
        logger.info("=" * 60)

        try:
            while self.running:
                self._process_pending_jobs()
                time.sleep(settings.worker_poll_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop()

    def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Scene Processing Worker Stopped")

    def _process_pending_jobs(self):
        """Poll for and process pending scene jobs."""
        try:
            jobs = self.db.get_pending_scene_jobs(limit=settings.max_concurrent_tasks)

            if not jobs:
                return

            logger.info(f"Found {len(jobs)} pending scene jobs")

            for job in jobs:
                try:
                    self._process_job(job)
                except Exception as e:
                    logger.error(f"Error processing job {job['job_id']}: {e}")
                    logger.error(traceback.format_exc())
                    self.db.update_scene_job_status(
                        job["job_id"],
                        SceneJobStatus.FAILED,
                        error_message=str(e)
                    )
        except Exception as e:
            logger.error(f"Error polling jobs: {e}")
            logger.error(traceback.format_exc())

    def _process_job(self, job: dict):
        """Process a single scene job with top-level exception handler."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})

        logger.info(f"Processing scene job {job_id} for video {video_id}")

        try:
            # Update status to processing
            self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING)

            # Process the scene
            self._process_scene(job)
        except KeyboardInterrupt:
            # Re-raise keyboard interrupt to allow graceful shutdown
            raise
        except Exception as e:
            # Catch ALL exceptions including system-level crashes
            error_msg = f"Critical error in job {job_id}: {type(e).__name__}: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())

            # Update job status to failed
            try:
                self.db.update_scene_job_status(
                    job_id,
                    SceneJobStatus.FAILED,
                    error_message=error_msg
                )
            except Exception as db_error:
                logger.error(f"Failed to update job status to FAILED: {db_error}")

            # Don't re-raise - continue processing other jobs
            logger.info(f"Continuing to next job after failure in {job_id}")

    def _process_scene(self, job: dict):
        """
        Process a scene from already-compressed video (from media workflow):
        1. Get compressed video path from job config
        2. Chunk the video (if chunk_duration > 0)
        3. Analyze each chunk with Gemini → save prompt and results to DB
        """
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})

        # Job status already set to processing in _process_job

        compressed_video_path = config.get("compressed_video_path")
        chunk_duration = config.get("chunk_duration", 30)
        should_chunk = config.get("chunk", True)
        context_items = config.get("context_items", [])

        logger.info(f"=== Scene worker processing ===")
        logger.info(f"video_id: {video_id}")
        logger.info(f"config: {config}")
        logger.info(f"chunk_duration from config: {chunk_duration} (type: {type(chunk_duration).__name__})")
        logger.info(f"should_chunk: {should_chunk}")
        logger.info(f"compressed_video_path: {compressed_video_path}")
        if context_items:
            logger.info(f"context_items: {len(context_items)} file(s)")

        # Get video info
        video = self.db.get_video(video_id)
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        # Determine which video path to use (compressed or original)
        video_path_to_process = compressed_video_path
        if not video_path_to_process:
            logger.warning(f"No compressed video path provided for {video_id}. Falling back to original video.")
            video_path_to_process = video.get("gcs_path")

        if not video_path_to_process:
            raise ValueError(f"No video path available for processing video {video_id}")

        logger.info(f"Processing video from GCS path: {video_path_to_process}")

        # Download the video from GCS
        file_ext = Path(video_path_to_process).suffix or ".mp4"
        local_video_path = self.temp_dir / f"{video_id}_source{file_ext}"
        self.storage.download_file(video_path_to_process, local_video_path)

        processed_files = [local_video_path]
        manifest_data = {
            "processed_path": video_path_to_process
        }

        # Get the prompt text and type from the job
        prompt_text = job.get("prompt_text")
        if not prompt_text:
            raise ValueError(f"Prompt text not found in scene job: {job_id}")

        prompt_type = job.get("prompt_type", "scene_analysis")
        logger.info(f"Using prompt_type: {prompt_type}")

        try:
            # ===== STEP 1: Chunk the video (if needed) =====
            if should_chunk and chunk_duration > 0:
                logger.info(f"[STEP 1/2] Chunking video into {chunk_duration}s segments for {video_id}")
                self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "chunking"})

                chunks_dir = self.temp_dir / f"{video_id}_chunks"

                # Get expected duration from video metadata (more reliable than probing extracted audio)
                expected_duration = video.get("metadata", {}).get("duration")
                if expected_duration:
                    logger.info(f"Using expected duration from metadata: {expected_duration:.2f}s")

                chunks = chunk_video(
                    input_path=local_video_path,
                    output_dir=chunks_dir,
                    chunk_duration=chunk_duration,
                    expected_duration=expected_duration
                )

                # Upload chunks to GCS
                for chunk in chunks:
                    chunk_path = Path(chunk["path"])
                    chunk_gcs = f"gs://{settings.processed_bucket}/{video_id}/scene_chunks/{chunk['filename']}"
                    self.storage.upload_file(chunk_path, chunk_gcs, "video/mp4")
                    chunk["gcs_path"] = chunk_gcs
                    processed_files.append(chunk_path)

                manifest_data["chunks"] = chunks
                logger.info(f"Created {len(chunks)} chunks and uploaded to GCS")
            else:
                # No chunking - treat entire video as one chunk
                logger.info(f"[STEP 1/2] No chunking - analyzing entire video for {video_id}")
                chunks = [{
                    "index": 0,
                    "filename": local_video_path.name,
                    "gcs_path": video_path_to_process,
                    "local_path": str(local_video_path),  # Use already-downloaded file
                    "duration": video.get("metadata", {}).get("duration", 0)
                }]
                manifest_data["chunks"] = chunks

            # Create and save manifest
            self.db.create_manifest(video_id, manifest_data)

            # ===== STEP 2: Analyze each chunk with Gemini =====
            logger.info(f"[STEP 2/2] Analyzing {len(chunks)} chunk(s) with Gemini for {video_id}")
            self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "analyzing"})

            # Use scene processor (sequential or parallel based on config)
            self.scene_processor.process_chunks(
                chunks=chunks,
                job_id=job_id,
                video_id=video_id,
                prompt_text=prompt_text,
                prompt_type=prompt_type,
                context_items=context_items if context_items else None
            )

            # Calculate aggregated stats
            job_results = self.db.get_results_for_job(job_id)
            total_tokens = 0
            total_cost = 0.0
            total_input_cost = 0.0
            total_output_cost = 0.0

            for res in job_results:
                usage = res.get("result_data", {}).get("token_usage", {})
                total_tokens += usage.get("total_tokens", 0)
                total_cost += usage.get("estimated_cost_usd", 0.0)
                total_input_cost += usage.get("input_cost_usd", 0.0)
                total_output_cost += usage.get("output_cost_usd", 0.0)

            token_usage_summary = {
                "total_tokens": total_tokens,
                "estimated_cost_usd": round(total_cost, 6),
                "input_cost_usd": round(total_input_cost, 6),
                "output_cost_usd": round(total_output_cost, 6)
            }

            # Update scene job status to completed
            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.COMPLETED,
                results={
                    "manifest_created": True,
                    "chunks_analyzed": len(chunks),
                    "step": "completed",
                    "token_usage": token_usage_summary
                }
            )

            logger.info(f"Successfully processed scene for video {video_id}")

        finally:
            # Clean up local files
            for file_path in processed_files:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted temp file: {file_path}")

def main():
    """Main entry point."""
    worker = SceneWorker()
    worker.start()


if __name__ == "__main__":
    main()
