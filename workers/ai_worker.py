"""
AI Processing Worker
Polls Firestore for pending scene processing and image adaptation tasks and executes them.
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
from libs.database import get_db, SceneJobStatus, ImageJobStatus
from libs.storage import get_storage
from libs.video_processing import chunk_video
from libs.gemini import get_scene_analyzer
from libs.gemini.image_analyzer import get_image_analyzer
from libs.scene_processing import get_scene_processor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AIWorker:
    """Worker for processing both scene and image AI jobs."""

    def __init__(self):
        """Initialize worker."""
        self.db = get_db()
        self.storage = get_storage()
        self.scene_analyzer = get_scene_analyzer()
        self.image_analyzer = get_image_analyzer()
        self.temp_dir = settings.get_temp_dir()
        self.running = False

        # Initialize scene processor
        self.scene_processor = get_scene_processor(
            db=self.db,
            storage=self.storage,
            analyzer=self.scene_analyzer,
            temp_dir=self.temp_dir,
        )

    def start(self):
        """Start the worker loop."""
        self.running = True

        logger.info("=" * 60)
        logger.info("AI Processing Worker Started")
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
        logger.info("AI Processing Worker Stopped")

    def _process_pending_jobs(self):
        """Poll for and process pending jobs of all types."""
        try:
            # 1. Check for pending image jobs first (usually faster)
            image_jobs = self.db.get_pending_image_jobs(limit=settings.max_concurrent_tasks)
            if image_jobs:
                logger.info(f"Found {len(image_jobs)} pending image jobs")
                for job in image_jobs:
                    self._process_image_job(job)

            # 2. Check for pending scene jobs
            scene_jobs = self.db.get_pending_scene_jobs(limit=settings.max_concurrent_tasks)
            if scene_jobs:
                logger.info(f"Found {len(scene_jobs)} pending scene jobs")
                for job in scene_jobs:
                    self._process_scene_job(job)

        except Exception as e:
            logger.error(f"Error polling jobs: {e}")
            logger.error(traceback.format_exc())

    def _process_image_job(self, job: dict):
        """Process a generative image adaptation job."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})

        logger.info(f"[IMAGE] Processing job {job_id} for asset {video_id}")

        try:
            self.db.update_image_job_status(job_id, ImageJobStatus.PROCESSING)

            # Get source asset info
            asset = self.db.get_video(video_id)
            if not asset:
                raise ValueError(f"Asset not found: {video_id}")

            # Download source image
            local_source_path = self.temp_dir / f"{video_id}_source_image"
            self.storage.download_file(asset["gcs_path"], local_source_path)

            with open(local_source_path, "rb") as f:
                image_bytes = f.read()

            target_ratios = config.get("aspect_ratios", [])
            resolution = config.get("resolution", "HD")
            prompt_text = job.get("prompt_text")

            total_usage = {"input_tokens": 0, "output_tokens": 0}
            last_stop_reason = "completed"

            # Process requested aspect ratios in parallel
            logger.info(f"[IMAGE] Generating {len(target_ratios)} adapts in parallel for {job_id}")

            gen_results = self.image_analyzer.generate_multiple_adapts(
                image_bytes=image_bytes,
                target_ratios=target_ratios,
                target_resolution=resolution,
                prompt_text=prompt_text,
            )

            for result in gen_results:
                if "error" in result:
                    logger.error(f"[IMAGE] Failed to generate {result.get('ratio')}: {result['error']}")
                    continue

                ratio = result["ratio"]

                # Save binary result to GCS
                safe_ratio = ratio.replace(":", "_")
                gcs_path = f"gs://{settings.results_bucket}/adapts/{job_id}/{safe_ratio}.jpg"

                self.storage.upload_bytes(result["image_bytes"], gcs_path, "image/jpeg")

                # Save individual result record
                self.db.save_image_result(
                    job_id=job_id,
                    video_id=video_id,
                    aspect_ratio=ratio,
                    gcs_path=gcs_path,
                    metadata={
                        "resolution": resolution,
                        "usage": result.get("usage", {}),
                        "stop_reason": result.get("stop_reason"),
                    },
                )

                # Aggregate usage
                usage = result.get("usage", {})
                total_usage["input_tokens"] += usage.get("input_tokens", 0)
                total_usage["output_tokens"] += usage.get("output_tokens", 0)
                last_stop_reason = result.get("stop_reason", last_stop_reason)

            # Update job to completed
            self.db.update_image_job_status(
                job_id,
                ImageJobStatus.COMPLETED,
                usage=total_usage,
                stop_reason=last_stop_reason,
            )

            # Clean up
            if local_source_path.exists():
                local_source_path.unlink()

        except Exception as e:
            logger.error(f"[IMAGE] Job {job_id} failed: {e}")
            self.db.update_image_job_status(job_id, ImageJobStatus.FAILED, error_message=str(e))

    def _process_scene_job(self, job: dict):
        """Process a single scene job with top-level exception handler."""
        job_id = job["job_id"]
        video_id = job["video_id"]

        logger.info(f"[SCENE] Processing job {job_id} for video {video_id}")

        try:
            # Update status to processing
            self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING)

            # Process the scene
            self._process_scene(job)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            error_msg = f"Critical error in job {job_id}: {type(e).__name__}: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())

            try:
                self.db.update_scene_job_status(job_id, SceneJobStatus.FAILED, error_message=error_msg)
            except Exception as db_error:
                logger.error(f"Failed to update job status to FAILED: {db_error}")

    def _process_scene(self, job: dict):
        """Legacy _process_scene logic for video/audio analysis."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})

        compressed_video_path = config.get("compressed_video_path")
        chunk_duration = config.get("chunk_duration", 30)
        should_chunk = config.get("chunk", True)
        context_items = config.get("context_items", [])

        # Get video info
        video = self.db.get_video(video_id)
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        video_path_to_process = compressed_video_path or video.get("gcs_path")
        if not video_path_to_process:
            raise ValueError(f"No video path available for processing video {video_id}")

        # Download the video from GCS
        file_ext = Path(video_path_to_process).suffix or ".mp4"
        local_video_path = self.temp_dir / f"{video_id}_source{file_ext}"
        self.storage.download_file(video_path_to_process, local_video_path)

        processed_files = [local_video_path]
        manifest_data = {"processed_path": video_path_to_process}

        prompt_text = job.get("prompt_text")
        prompt_type = job.get("prompt_type", "scene_analysis")

        try:
            # Chunking
            if should_chunk and chunk_duration > 0:
                self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "chunking"})
                chunks_dir = self.temp_dir / f"{video_id}_chunks"
                expected_duration = video.get("metadata", {}).get("duration")

                chunks = chunk_video(
                    input_path=local_video_path,
                    output_dir=chunks_dir,
                    chunk_duration=chunk_duration,
                    expected_duration=expected_duration,
                )

                for chunk in chunks:
                    chunk_path = Path(chunk["path"])
                    chunk_gcs = f"gs://{settings.processed_bucket}/{video_id}/scene_chunks/{chunk['filename']}"
                    self.storage.upload_file(chunk_path, chunk_gcs, "video/mp4")
                    chunk["gcs_path"] = chunk_gcs
                    processed_files.append(chunk_path)

                manifest_data["chunks"] = chunks
            else:
                chunks = [
                    {
                        "index": 0,
                        "filename": local_video_path.name,
                        "gcs_path": video_path_to_process,
                        "local_path": str(local_video_path),
                        "duration": video.get("metadata", {}).get("duration", 0),
                    }
                ]
                manifest_data["chunks"] = chunks

            self.db.create_manifest(video_id, manifest_data)

            # Analysis
            self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "analyzing"})
            self.scene_processor.process_chunks(
                chunks=chunks,
                job_id=job_id,
                video_id=video_id,
                prompt_text=prompt_text,
                prompt_type=prompt_type,
                context_items=context_items,
            )

            # Finalize
            job_results = self.db.get_results_for_job(job_id)
            total_tokens = 0
            total_cost = 0.0
            last_stop_reason = "completed"

            for res in job_results:
                usage = res.get("result_data", {}).get("token_usage", {})
                total_tokens += usage.get("total_tokens", 0)
                total_cost += usage.get("estimated_cost_usd", 0.0)
                # Capture stop reason from chunks
                last_stop_reason = res.get("result_data", {}).get("finish_reason", last_stop_reason)

            self.db.update_scene_job_status(
                job_id,
                SceneJobStatus.COMPLETED,
                results={
                    "manifest_created": True,
                    "chunks_analyzed": len(chunks),
                    "step": "completed",
                    "token_usage": {
                        "total_tokens": total_tokens,
                        "estimated_cost_usd": round(total_cost, 6),
                    },
                },
                stop_reason=last_stop_reason,
            )

        finally:
            for file_path in processed_files:
                if file_path.exists():
                    file_path.unlink()


def main():
    """Main entry point."""
    from workers.health import start_health_server

    start_health_server()

    worker = AIWorker()
    worker.start()


if __name__ == "__main__":
    main()
