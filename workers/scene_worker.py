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
from libs.database import get_db, TaskStatus, SceneJobStatus
from libs.storage import get_storage
from libs.video_processing import (
    extract_metadata,
    compress_video,
    chunk_video,
    extract_audio,
    create_manifest
)
from libs.gemini import get_scene_analyzer

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
                self._process_pending_tasks()
                time.sleep(settings.worker_poll_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop()

    def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Scene Processing Worker Stopped")

    def _process_pending_tasks(self):
        """Poll for and process pending tasks."""
        try:
            tasks = self.db.get_pending_tasks(limit=settings.max_concurrent_tasks)

            if not tasks:
                return

            logger.info(f"Found {len(tasks)} pending tasks")

            for task in tasks:
                try:
                    self._process_task(task)
                except Exception as e:
                    logger.error(f"Error processing task {task['task_id']}: {e}")
                    logger.error(traceback.format_exc())
                    self.db.update_task_status(
                        task["task_id"],
                        TaskStatus.FAILED,
                        error_message=str(e)
                    )
                    # Also update the scene job status to failed
                    if task.get("scene_job_id"):
                        self.db.update_scene_job_status(
                            task["scene_job_id"],
                            SceneJobStatus.FAILED,
                            error_message=str(e)
                        )
        except Exception as e:
            logger.error(f"Error polling tasks: {e}")
            logger.error(traceback.format_exc())

    def _process_task(self, task: dict):
        """Process a single task."""
        task_id = task["task_id"]
        video_id = task["video_id"]
        scene_job_id = task.get("scene_job_id")

        if not scene_job_id:
            raise ValueError(f"Task {task_id} is missing a scene_job_id")

        logger.info(f"Processing task {task_id}: {task_type} for video {video_id}")

        # Update status to processing
        self.db.update_task_status(task_id, TaskStatus.PROCESSING)

        if task_type == "scene_processing":
            self._process_scene(task)
        elif task_type == "video_processing":
            # Legacy support - redirect to scene processing
            self._process_scene(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    def _process_scene(self, task: dict):
        """
        Process a scene from already-compressed video (from media workflow):
        1. Get compressed video path from task input
        2. Chunk the video (if chunk_duration > 0)
        3. Analyze each chunk with Gemini → save prompt and results to DB
        """
        task_id = task["task_id"]
        video_id = task["video_id"]
        scene_job_id = task["scene_job_id"]
        input_data = task.get("input_data", {})

        # Update job status to processing
        self.db.update_scene_job_status(scene_job_id, SceneJobStatus.PROCESSING)

        compressed_video_path = input_data.get("compressed_video_path")
        chunk_duration = input_data.get("chunk_duration", 30)
        should_chunk = input_data.get("chunk", True)

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

        try:
            # ===== STEP 1: Chunk the video (if needed) =====
            if should_chunk and chunk_duration > 0:
                logger.info(f"[STEP 1/2] Chunking video into {chunk_duration}s segments for {video_id}")
                self.db.update_scene_job_status(scene_job_id, SceneJobStatus.PROCESSING, {"step": "chunking"})

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
                    "filename": "full_video.mp4",
                    "gcs_path": compressed_video_path,
                    "duration": video.get("metadata", {}).get("duration", 0)
                }]
                manifest_data["chunks"] = chunks

            # Create and save manifest
            self.db.create_manifest(video_id, manifest_data)

            # ===== STEP 2: Analyze each chunk with Gemini =====
            logger.info(f"[STEP 2/2] Analyzing {len(chunks)} chunk(s) with Gemini for {video_id}")
            self.db.update_scene_job_status(scene_job_id, SceneJobStatus.PROCESSING, {"step": "analyzing"})

            # Get the prompt text once for all chunks
            prompt_text = self.analyzer.get_prompt_text()

            for chunk in chunks:
                chunk_index = chunk["index"]
                chunk_gcs = chunk["gcs_path"]

                logger.info(f"Analyzing chunk {chunk_index + 1}/{len(chunks)}")

                # Update progress in metadata
                self.db.update_scene_job_status(
                    scene_job_id,
                    SceneJobStatus.PROCESSING,
                    results={
                        "progress": {
                            "completed_chunks": chunk_index,
                            "total_chunks": len(chunks)
                        }
                    }
                )

                # Download chunk from GCS
                local_chunk_path = self.temp_dir / f"{video_id}_{chunk['filename']}"
                self.storage.download_file(chunk_gcs, local_chunk_path)

                try:
                    # Save prompt to database
                    prompt_id = self.db.save_prompt(
                        video_id=video_id,
                        chunk_index=chunk_index,
                        prompt_text=prompt_text,
                        prompt_type="scene_analysis"
                    )
                    logger.info(f"Saved prompt {prompt_id} for chunk {chunk_index}")

                    # Analyze with Gemini
                    result = self.analyzer.analyze_chunk(
                        video_path=local_chunk_path,
                        chunk_index=chunk_index,
                        chunk_duration=chunk["duration"]
                    )

                    # Save result to database
                    result_id = self.db.save_result(
                        video_id=video_id,
                        result_type="scene_analysis",
                        result_data=result
                    )
                    logger.info(f"Saved analysis result {result_id} for chunk {chunk_index}")

                    # Update progress after successful scene analysis
                    self.db.update_scene_job_status(
                        scene_job_id,
                        SceneJobStatus.PROCESSING,
                        results={
                            "progress": {
                                "completed_chunks": chunk_index + 1,
                                "total_chunks": len(chunks)
                            }
                        }
                    )

                finally:
                    # Clean up chunk file
                    if local_chunk_path.exists():
                        local_chunk_path.unlink()

                        # Update scene job status to completed            self.db.update_scene_job_status(                scene_job_id,                SceneJobStatus.COMPLETED,                results={                    "manifest_created": True,                    "chunks_analyzed": len(chunks)                }            )            # Mark task as completed            self.db.update_task_status(                task_id,                TaskStatus.COMPLETED,                result_data={                    "message": "Scene job completed successfully"                }            )

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
