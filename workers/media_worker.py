"""
Media Processing Worker
Polls Firestore for pending media processing jobs and executes them.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
import time
import traceback
from config import settings
from libs.database import get_db, MediaJobStatus
from libs.storage import get_storage
from libs.media_processor import MediaProcessor, MediaProcessingConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MediaWorker:
    """Worker for processing media jobs."""

    def __init__(self):
        """Initialize worker."""
        self.db = get_db()
        self.storage = get_storage()
        self.temp_dir = settings.get_temp_dir()
        self.processor = MediaProcessor(self.temp_dir)
        self.running = False

    def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info("=" * 60)
        logger.info("Media Processing Worker Started")
        logger.info(f"Polling interval: {settings.worker_poll_interval_seconds}s")
        logger.info(f"Max concurrent jobs: {settings.max_concurrent_tasks}")
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
        logger.info("Media Processing Worker Stopped")

    def _process_pending_jobs(self):
        """Poll for and process pending media jobs."""
        try:
            jobs = self.db.get_pending_media_jobs(limit=settings.max_concurrent_tasks)

            if not jobs:
                return

            logger.info(f"Found {len(jobs)} pending media jobs")

            for job in jobs:
                try:
                    self._process_job(job)
                except Exception as e:
                    logger.error(f"Error processing job {job['job_id']}: {e}")
                    logger.error(traceback.format_exc())
                    self.db.update_media_job_status(
                        job["job_id"],
                        MediaJobStatus.FAILED,
                        error_message=str(e)
                    )

        except Exception as e:
            logger.error(f"Error polling jobs: {e}")
            logger.error(traceback.format_exc())

    def _process_job(self, job: dict):
        """Process a single media job."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config_dict = job["config"]

        logger.info(f"Processing media job {job_id} for video {video_id}")

        # Update status to processing
        self.db.update_media_job_status(job_id, MediaJobStatus.PROCESSING)

        # Get video info
        video = self.db.get_video(video_id)
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        # Download video from GCS
        local_video_path = self.temp_dir / f"{video_id}_original.mp4"
        self.storage.download_file(video["gcs_path"], local_video_path)

        processed_files = [local_video_path]

        try:
            # Create processing config
            config = MediaProcessingConfig(
                compress=config_dict.get("compress", True),
                compress_resolution=config_dict.get("compress_resolution", "480p"),
                extract_audio=config_dict.get("extract_audio", True),
                audio_format=config_dict.get("audio_format", "mp3"),
                audio_bitrate=config_dict.get("audio_bitrate", "128k"),
                crf=config_dict.get("crf", 23),
                preset=config_dict.get("preset", "medium")
            )

            # Progress callback
            def progress_callback(step: str, progress: int):
                logger.info(f"Job {job_id} - {step}: {progress}%")
                self.db.update_media_job_status(
                    job_id,
                    MediaJobStatus.PROCESSING,
                    progress={"step": step, "percent": progress}
                )

            # Process the video
            result = self.processor.process(
                input_path=local_video_path,
                video_id=video_id,
                config=config,
                progress_callback=progress_callback
            )

            if result.error:
                raise Exception(result.error)

            # Upload processed files to GCS
            results_data = {
                "metadata": result.metadata,
                "original_size_bytes": result.original_size_bytes,
                "compressed_size_bytes": result.compressed_size_bytes,
                "compression_ratio": result.compression_ratio,
                "audio_size_bytes": result.audio_size_bytes,
            }

            # Upload compressed video
            if result.compressed_video_path and result.compressed_video_path.exists():
                compressed_gcs = f"gs://{settings.processed_bucket}/{video_id}/media_compressed.mp4"
                self.storage.upload_file(
                    result.compressed_video_path,
                    compressed_gcs,
                    "video/mp4"
                )
                results_data["compressed_video_path"] = compressed_gcs
                processed_files.append(result.compressed_video_path)
                logger.info(f"Uploaded compressed video to {compressed_gcs}")

            # Upload audio
            if result.audio_path and result.audio_path.exists():
                audio_ext = config.audio_format
                audio_gcs = f"gs://{settings.processed_bucket}/{video_id}/media_audio.{audio_ext}"
                content_type = {
                    "mp3": "audio/mpeg",
                    "aac": "audio/aac",
                    "wav": "audio/wav"
                }.get(audio_ext, "audio/mpeg")

                self.storage.upload_file(
                    result.audio_path,
                    audio_gcs,
                    content_type
                )
                results_data["audio_path"] = audio_gcs
                processed_files.append(result.audio_path)
                logger.info(f"Uploaded audio to {audio_gcs}")

            # Update job status to completed
            self.db.update_media_job_status(
                job_id,
                MediaJobStatus.COMPLETED,
                results=results_data
            )

            logger.info(f"Successfully processed media job {job_id}")

        finally:
            # Clean up local files
            for file_path in processed_files:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Deleted temp file: {file_path}")


def main():
    """Main entry point."""
    worker = MediaWorker()
    worker.start()


if __name__ == "__main__":
    main()
