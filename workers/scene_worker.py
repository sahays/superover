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
from libs.database import get_db, TaskStatus, VideoStatus
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
                    # Also update the video status to failed
                    self.db.update_video_status(task["video_id"], VideoStatus.FAILED)

        except Exception as e:
            logger.error(f"Error polling tasks: {e}")
            logger.error(traceback.format_exc())

    def _process_task(self, task: dict):
        """Process a single task."""
        task_id = task["task_id"]
        task_type = task["task_type"]
        video_id = task["video_id"]

        logger.info(f"Processing task {task_id}: {task_type} for video {video_id}")

        # Update status to processing
        self.db.update_task_status(task_id, TaskStatus.PROCESSING)

        if task_type == "video_processing":
            self._process_video(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    def _process_video(self, task: dict):
        """
        Process a video following the 5-step workflow:
        1. Extract metadata → save to DB
        2. Extract audio tracks → save to DB
        3. Compress to 480p
        4. Chunk to 30 seconds → save chunks to GCS and paths to DB
        5. Analyze each chunk with Gemini → save prompt and results to DB
        """
        task_id = task["task_id"]
        video_id = task["video_id"]

        # Get video info
        video = self.db.get_video(video_id)
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        # Download video from GCS
        local_video_path = self.temp_dir / f"{video_id}_original.mp4"
        self.storage.download_file(video["gcs_path"], local_video_path)

        processed_files = [local_video_path]
        manifest_data = {}

        try:
            # ===== STEP 1: Extract Metadata =====
            logger.info(f"[STEP 1/5] Extracting metadata for {video_id}")
            self.db.update_video_status(video_id, VideoStatus.EXTRACTING_METADATA)

            metadata = extract_metadata(local_video_path)

            # Save metadata to DB
            self.db.update_video_metadata(video_id, metadata)
            logger.info(f"Metadata extracted: {metadata.get('duration')}s, {metadata.get('width')}x{metadata.get('height')}")

            # ===== STEP 2: Extract Audio =====
            logger.info(f"[STEP 2/5] Extracting audio for {video_id}")
            self.db.update_video_status(video_id, VideoStatus.EXTRACTING_AUDIO)

            audio_path = self.temp_dir / f"{video_id}_audio.mp3"
            extracted_audio = extract_audio(local_video_path, audio_path)

            audio_info = {}
            if extracted_audio:
                # Upload audio to GCS
                audio_gcs = f"gs://{settings.processed_bucket}/{video_id}/audio.mp3"
                self.storage.upload_file(audio_path, audio_gcs, "audio/mpeg")
                audio_info = {
                    "has_audio": True,
                    "gcs_path": audio_gcs,
                    "format": "mp3"
                }
                manifest_data["audio_path"] = audio_gcs
                processed_files.append(audio_path)
                logger.info(f"Audio extracted and uploaded to {audio_gcs}")
            else:
                audio_info = {"has_audio": False}
                logger.info(f"No audio stream found in video {video_id}")

            # Save audio info to DB
            self.db.update_video_audio_info(video_id, audio_info)

            # ===== STEP 3: Compress to 480p =====
            logger.info(f"[STEP 3/5] Compressing video to 480p for {video_id}")
            self.db.update_video_status(video_id, VideoStatus.COMPRESSING)

            compressed_path = self.temp_dir / f"{video_id}_compressed.mp4"
            compress_video(local_video_path, compressed_path)

            # Upload compressed video
            compressed_gcs = f"gs://{settings.processed_bucket}/{video_id}/compressed.mp4"
            self.storage.upload_file(compressed_path, compressed_gcs, "video/mp4")
            manifest_data["compressed_path"] = compressed_gcs
            processed_files.append(compressed_path)
            logger.info(f"Video compressed and uploaded to {compressed_gcs}")

            # ===== STEP 4: Chunk to 30 seconds =====
            logger.info(f"[STEP 4/5] Chunking video into {settings.chunk_duration_seconds}s segments for {video_id}")
            self.db.update_video_status(video_id, VideoStatus.CHUNKING)

            chunks_dir = self.temp_dir / f"{video_id}_chunks"
            chunks = chunk_video(compressed_path, chunks_dir)

            # Upload chunks to GCS
            for chunk in chunks:
                chunk_path = Path(chunk["path"])
                chunk_gcs = f"gs://{settings.processed_bucket}/{video_id}/chunks/{chunk['filename']}"
                self.storage.upload_file(chunk_path, chunk_gcs, "video/mp4")
                chunk["gcs_path"] = chunk_gcs
                processed_files.append(chunk_path)

            manifest_data["chunks"] = chunks
            logger.info(f"Created {len(chunks)} chunks and uploaded to GCS")

            # Create and save manifest
            manifest = create_manifest(
                video_id=video_id,
                original_metadata=metadata,
                **manifest_data
            )
            self.db.create_manifest(video_id, manifest)

            # ===== STEP 5: Analyze each chunk with Gemini =====
            logger.info(f"[STEP 5/5] Analyzing {len(chunks)} chunks with Gemini for {video_id}")
            self.db.update_video_status(video_id, VideoStatus.ANALYZING)

            # Get the prompt text once for all chunks
            prompt_text = self.analyzer.get_prompt_text()

            for chunk in chunks:
                chunk_index = chunk["index"]
                chunk_gcs = chunk["gcs_path"]

                logger.info(f"Analyzing chunk {chunk_index + 1}/{len(chunks)}")

                # Update progress in metadata
                self.db.update_video_metadata(video_id, {
                    "scene_analysis_progress": {
                        "completed_chunks": chunk_index,
                        "total_chunks": len(chunks)
                    }
                })

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
                    self.db.update_video_metadata(video_id, {
                        "scene_analysis_progress": {
                            "completed_chunks": chunk_index + 1,
                            "total_chunks": len(chunks)
                        }
                    })

                finally:
                    # Clean up chunk file
                    if local_chunk_path.exists():
                        local_chunk_path.unlink()

            # Update video status to completed
            self.db.update_video_status(video_id, VideoStatus.COMPLETED)

            # Mark task as completed
            self.db.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                result_data={
                    "manifest_created": True,
                    "chunks_analyzed": len(chunks)
                }
            )

            logger.info(f"Successfully processed video {video_id}")

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
