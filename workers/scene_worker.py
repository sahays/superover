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

    def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info("=" * 60)
        logger.info("Scene Processing Worker Started")
        logger.info(f"Polling interval: {settings.worker_poll_interval_seconds}s")
        logger.info(f"Max concurrent tasks: {settings.max_concurrent_tasks}")
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
        """Process a single scene job."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})

        logger.info(f"Processing scene job {job_id} for video {video_id}")

        # Update status to processing
        self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING)

        # Process the scene
        self._process_scene(job)

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

        logger.info(f"Processing scene for video {video_id} with chunk_duration={chunk_duration}s")

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

        # Get the prompt text from the job
        prompt_text = job.get("prompt_text")
        if not prompt_text:
            raise ValueError(f"Prompt text not found in scene job: {job_id}")

        try:
            # ===== STEP 1: Chunk the video (if needed) =====
            if should_chunk and chunk_duration > 0:
                logger.info(f"[STEP 1/2] Chunking video into {chunk_duration}s segments for {video_id}")
                self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "chunking"})

                chunks_dir = self.temp_dir / f"{video_id}_chunks"
                chunks = chunk_video(
                    input_path=local_video_path,
                    output_dir=chunks_dir,
                    chunk_duration=chunk_duration
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
                    # Analyze with Gemini
                    result = self.analyzer.analyze_chunk(
                        video_path=local_chunk_path,
                        chunk_index=chunk_index,
                        chunk_duration=chunk["duration"],
                        prompt_text=prompt_text,  # Pass the prompt text
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

            # Update scene job status to completed
            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.COMPLETED,
                results={
                    "manifest_created": True,
                    "chunks_analyzed": len(chunks),
                    "step": "completed"
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
