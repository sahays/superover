"""
Unified Worker
Merges media processing and AI analysis into a single polling loop.
Media jobs use the Transcoder API (non-blocking). AI jobs use Gemini directly.
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
from libs.database import get_db, MediaJobStatus, SceneJobStatus, ImageJobStatus
from libs.storage import get_storage
from libs.transcoder import get_transcoder_client
from libs.gemini import get_scene_analyzer
from libs.gemini.image_analyzer import get_image_analyzer
from libs.scene_processing import get_scene_processor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UnifiedWorker:
    """Unified worker processing media, scene, and image jobs."""

    def __init__(self):
        """Initialize worker with all required clients."""
        self.db = get_db()
        self.storage = get_storage()
        self.transcoder = get_transcoder_client()
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
        """Start the unified worker loop."""
        self.running = True

        logger.info("=" * 60)
        logger.info("Unified Worker Started")
        logger.info(f"Polling interval: {settings.worker_poll_interval_seconds}s")
        logger.info(f"Max concurrent tasks: {settings.max_concurrent_tasks}")
        logger.info(f"Transcoder location: {settings.transcoder_location}")
        logger.info("=" * 60)

        try:
            while self.running:
                self._poll_cycle()
                time.sleep(settings.worker_poll_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop()

    def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Unified Worker Stopped")

    def _poll_cycle(self):
        """Execute one poll cycle across all job types."""
        try:
            # 1. Check in-flight Transcoder jobs (non-blocking poll)
            self._check_transcoding_jobs()

            # 2. Submit new pending media jobs to Transcoder API
            self._process_pending_media_jobs()

            # 3. Process pending image adaptation jobs (Gemini)
            self._process_pending_image_jobs()

            # 4. Process pending scene analysis jobs (Gemini)
            self._process_pending_scene_jobs()

        except Exception as e:
            logger.error(f"Error in poll cycle: {e}")
            logger.error(traceback.format_exc())

    # ── Media Jobs (Transcoder API) ──────────────────────────

    def _check_transcoding_jobs(self):
        """Poll Transcoder API for in-flight media jobs."""
        try:
            jobs = self.db.get_transcoding_media_jobs(limit=20)
            if not jobs:
                return

            for job in jobs:
                try:
                    self._check_single_transcoding_job(job)
                except Exception as e:
                    logger.error(f"Error checking transcoding job {job['job_id']}: {e}")
                    logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"Error polling transcoding jobs: {e}")

    def _check_single_transcoding_job(self, job: dict):
        """Check status of a single Transcoder API job."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        transcoder_job_name = job.get("transcoder_job_name")
        config_dict = job.get("config", {})

        if not transcoder_job_name:
            logger.warning(f"Media job {job_id} in TRANSCODING state but missing transcoder_job_name")
            self.db.update_media_job_status(
                job_id, MediaJobStatus.FAILED, error_message="Missing transcoder job reference"
            )
            return

        status = self.transcoder.get_job_status(transcoder_job_name)

        if status["state"] == "SUCCEEDED":
            logger.info(f"Transcoder job completed for media job {job_id}")

            # Build results from Transcoder output
            output_prefix = status["output_uri"]
            video = self.db.get_video(video_id)
            input_gcs_uri = video.get("gcs_path") if video else None
            results_data = {
                "metadata": self.transcoder.extract_metadata_from_job(transcoder_job_name, input_gcs_uri=input_gcs_uri),
            }

            # Store duration on the video record so scene jobs can access it
            duration = results_data["metadata"].get("duration")
            if duration and video:
                self.db.update_video_metadata(video_id, {"duration": duration})

            # Determine output paths based on config
            if config_dict.get("compress", True):
                compressed_path = f"{output_prefix}media_compressed.mp4"
                results_data["compressed_video_path"] = compressed_path

                # Get file sizes from GCS
                try:
                    meta = self.storage.get_file_metadata(compressed_path)
                    results_data["compressed_size_bytes"] = meta.get("size", 0)
                except Exception:
                    results_data["compressed_size_bytes"] = 0

            if config_dict.get("extract_audio", True):
                audio_format = config_dict.get("audio_format", "aac")
                audio_ext = "m4a" if audio_format == "aac" else audio_format
                audio_path = f"{output_prefix}media_audio.{audio_ext}"
                results_data["audio_path"] = audio_path

                try:
                    meta = self.storage.get_file_metadata(audio_path)
                    results_data["audio_size_bytes"] = meta.get("size", 0)
                except Exception:
                    results_data["audio_size_bytes"] = 0

            # Get original file size
            video = self.db.get_video(video_id)
            if video:
                results_data["original_size_bytes"] = video.get("size_bytes", 0)
                compressed_bytes = results_data.get("compressed_size_bytes", 0)
                original_bytes = results_data["original_size_bytes"]
                if original_bytes > 0 and compressed_bytes > 0:
                    results_data["compression_ratio"] = round((1 - compressed_bytes / original_bytes) * 100, 1)
                else:
                    results_data["compression_ratio"] = 0.0

            self.db.update_media_job_status(job_id, MediaJobStatus.COMPLETED, results=results_data)
            logger.info(f"Media job {job_id} completed successfully")

        elif status["state"] == "FAILED":
            error_msg = status.get("error", "Transcoder job failed")
            logger.error(f"Transcoder job failed for media job {job_id}: {error_msg}")
            self.db.update_media_job_status(job_id, MediaJobStatus.FAILED, error_message=error_msg)

        else:
            # PENDING or RUNNING — still in progress
            logger.debug(f"Transcoder job for {job_id} still {status['state']}")

    def _process_pending_media_jobs(self):
        """Submit pending media jobs to the Transcoder API."""
        try:
            jobs = self.db.get_pending_media_jobs(limit=settings.max_concurrent_tasks)
            if not jobs:
                return

            logger.info(f"Found {len(jobs)} pending media jobs")

            for job in jobs:
                try:
                    self._submit_media_job(job)
                except Exception as e:
                    logger.error(f"Error submitting media job {job['job_id']}: {e}")
                    logger.error(traceback.format_exc())
                    self.db.update_media_job_status(job["job_id"], MediaJobStatus.FAILED, error_message=str(e))

        except Exception as e:
            logger.error(f"Error polling pending media jobs: {e}")

    def _submit_media_job(self, job: dict):
        """Submit a single media job to the Transcoder API (PENDING -> TRANSCODING)."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config_dict = job["config"]

        logger.info(f"Submitting media job {job_id} for video {video_id}")

        # Get video info
        video = self.db.get_video(video_id)
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        input_gcs_uri = video["gcs_path"]
        output_gcs_prefix = f"gs://{settings.processed_bucket}/{video_id}/"

        # Submit to Transcoder API
        transcoder_job_name = self.transcoder.submit_media_job(
            input_gcs_uri=input_gcs_uri,
            output_gcs_prefix=output_gcs_prefix,
            compress=config_dict.get("compress", True),
            resolution=config_dict.get("compress_resolution", "480p"),
            crf=config_dict.get("crf", 23),
            extract_audio=config_dict.get("extract_audio", True),
            audio_format=config_dict.get("audio_format", "aac"),
            audio_bitrate=config_dict.get("audio_bitrate", "128k"),
        )

        # Update job to TRANSCODING state with reference
        self.db.update_media_job_transcoder(job_id, transcoder_job_name, phase="media")
        logger.info(f"Media job {job_id} submitted to Transcoder: {transcoder_job_name}")

    # ── Image Jobs (Gemini) ──────────────────────────────────

    def _process_pending_image_jobs(self):
        """Process pending image adaptation jobs."""
        try:
            jobs = self.db.get_pending_image_jobs(limit=settings.max_concurrent_tasks)
            if not jobs:
                return

            logger.info(f"Found {len(jobs)} pending image jobs")

            for job in jobs:
                try:
                    self._process_image_job(job)
                except Exception as e:
                    logger.error(f"Error processing image job {job.get('job_id')}: {e}")
                    logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Error polling image jobs: {e}")

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

    # ── Scene Jobs (Gemini + Transcoder for chunking) ────────

    def _process_pending_scene_jobs(self):
        """Process pending scene analysis jobs."""
        try:
            jobs = self.db.get_pending_scene_jobs(limit=settings.max_concurrent_tasks)
            if not jobs:
                return

            logger.info(f"Found {len(jobs)} pending scene jobs")

            for job in jobs:
                try:
                    self._process_scene_job(job)
                except Exception as e:
                    logger.error(f"Error processing scene job {job.get('job_id')}: {e}")
                    logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Error polling scene jobs: {e}")

    def _process_scene_job(self, job: dict):
        """Process a single scene job with top-level exception handler."""
        job_id = job["job_id"]
        video_id = job["video_id"]

        logger.info(f"[SCENE] Processing job {job_id} for video {video_id}")

        try:
            self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING)
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
        """Process a scene analysis job using Transcoder API for chunking."""
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

        prompt_text = job.get("prompt_text")
        prompt_type = job.get("prompt_type", "scene_analysis")
        response_schema = job.get("response_schema")

        manifest_data = {"processed_path": video_path_to_process}

        # Chunking via Transcoder API
        if should_chunk and chunk_duration > 0:
            self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "chunking"})

            total_duration = video.get("metadata", {}).get("duration")
            if not total_duration:
                logger.warning(
                    f"Video {video_id} has no duration metadata. "
                    f"Falling back to no-chunking mode (processing entire video as single chunk)."
                )
                # Fall back to single-chunk mode
                chunks = [
                    {
                        "index": 0,
                        "filename": Path(video_path_to_process).name,
                        "gcs_path": video_path_to_process,
                        "duration": 0,
                    }
                ]
                manifest_data["chunks"] = chunks
            else:
                output_prefix = f"gs://{settings.processed_bucket}/{video_id}/scene_chunks/"

                # Submit chunking job and wait for completion (blocking)
                transcoder_job_name = self.transcoder.submit_chunking_job(
                    input_gcs_uri=video_path_to_process,
                    output_gcs_prefix=output_prefix,
                    chunk_duration=chunk_duration,
                    total_duration=total_duration,
                )

                status = self.transcoder.wait_for_completion(transcoder_job_name)
                if status["state"] != "SUCCEEDED":
                    raise Exception(f"Chunking failed: {status.get('error', 'Unknown error')}")

                # Build chunk list from expected output paths
                chunks = self.transcoder.build_chunk_list(output_prefix, chunk_duration, total_duration)
                manifest_data["chunks"] = chunks
        else:
            # No chunking — process the entire video as a single chunk
            duration = video.get("metadata", {}).get("duration", 0)
            chunks = [
                {
                    "index": 0,
                    "filename": Path(video_path_to_process).name,
                    "gcs_path": video_path_to_process,
                    "duration": duration,
                }
            ]
            manifest_data["chunks"] = chunks

        self.db.create_manifest(video_id, manifest_data)

        # Analysis — chunks are already in GCS, pass GCS URIs to scene processor
        self.db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "analyzing"})
        self.scene_processor.process_chunks(
            chunks=chunks,
            job_id=job_id,
            video_id=video_id,
            prompt_text=prompt_text,
            prompt_type=prompt_type,
            context_items=context_items,
            response_schema=response_schema,
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


def main():
    """Main entry point."""
    from workers.health import start_health_server

    start_health_server()

    worker = UnifiedWorker()
    worker.start()


if __name__ == "__main__":
    main()
