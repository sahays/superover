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

import asyncio
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import cast
from config import settings
from libs.database import get_db, MediaJobStatus, SceneJobStatus, ImageJobStatus
from libs.db.enums import EngagementJobStatus, DubbingJobStatus
from libs.storage import get_storage
from libs.transcoder import get_transcoder_client
from libs.gemini import get_scene_analyzer, get_engagement_analyzer
from libs.gemini.image_analyzer import get_image_analyzer
from libs.gemini.dubbing_engine import get_dubbing_engine
from libs.scene_processing import get_scene_processor
from libs.scene_processing.orchestrator import SceneOrchestrator
from libs.engagement import parse_barc_csv, find_extrema, fetch_chunks_at
from libs.engagement.prompts import ENGAGEMENT_PROMPT_TEXT
from libs.engagement.scene_extract import (
    extract_from_scene_results,
    extract_key_moments,
    extract_narrative_beats,
    extract_segments,
)
from libs.engagement.recommendations import bind_callouts_to_minutes, compute_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UnifiedWorker:
    """Unified worker processing media, scene, image, and dubbing jobs."""

    def __init__(self):
        """Initialize worker with all required clients."""
        self.db = get_db()
        self.storage = get_storage()
        self.transcoder = get_transcoder_client()
        self.scene_analyzer = get_scene_analyzer()
        self.image_analyzer = get_image_analyzer()
        self.engagement_analyzer = get_engagement_analyzer()
        self.dubbing_engine = get_dubbing_engine()
        self.temp_dir = settings.get_temp_dir()
        self.running = False

        # Initialize scene processor and orchestrator
        self.scene_processor = get_scene_processor(
            db=self.db,
            storage=self.storage,
            analyzer=self.scene_analyzer,
            temp_dir=self.temp_dir,
        )
        self.scene_orchestrator = SceneOrchestrator(
            transcoder=self.transcoder,
            scene_processor=self.scene_processor,
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

            # 5. Process pending engagement analysis jobs (deterministic + Gemini)
            self._process_pending_engagement_jobs()

            # 6. Process pending multilingual AI dubbing jobs
            self._process_pending_dubbing_jobs()

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

            if config_dict.get("extract_audio", True) or config_dict.get("dialog_mode", False):
                audio_format = config_dict.get("audio_format", "aac")
                audio_ext = "m4a" if audio_format == "aac" else audio_format
                is_dialog = config_dict.get("dialog_mode", False)
                file_label = "media_dialog" if is_dialog else "media_audio"
                audio_path = f"{output_prefix}{file_label}.{audio_ext}"
                results_data["audio_path"] = audio_path
                if is_dialog:
                    results_data["dialog_mode"] = True
                    # Dialog mode also produces a vocals_path for the scene analysis picker
                    results_data["vocals_path"] = audio_path

                try:
                    meta = self.storage.get_file_metadata(audio_path)
                    results_data["audio_size_bytes"] = meta.get("size", 0)
                    if is_dialog:
                        results_data["vocals_size_bytes"] = meta.get("size", 0)
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
            dialog_mode=config_dict.get("dialog_mode", False),
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
        self.scene_orchestrator.run(job)

    # ── Engagement Jobs (BARC + Gemini) ──────────────────────

    def _process_pending_engagement_jobs(self):
        """Process pending engagement analysis jobs."""
        try:
            jobs = self.db.get_pending_engagement_jobs(limit=settings.max_concurrent_tasks)
            if not jobs:
                return

            logger.info(f"Found {len(jobs)} pending engagement jobs")

            for job in jobs:
                try:
                    self._process_engagement_job(job)
                except Exception as e:
                    logger.error(f"Error processing engagement job {job.get('job_id')}: {e}")
                    logger.error(traceback.format_exc())
                    try:
                        self.db.update_engagement_job_status(
                            job["job_id"], EngagementJobStatus.FAILED, error_message=str(e)
                        )
                    except Exception as db_error:
                        logger.error(f"Failed to mark engagement job FAILED: {db_error}")

        except Exception as e:
            logger.error(f"Error polling engagement jobs: {e}")

    def _process_engagement_job(self, job: dict):
        """Run a single engagement analysis job end-to-end."""
        import json as _json

        job_id = job["job_id"]
        video_id = job["video_id"]
        source_scene_job_id = job["source_scene_job_id"]
        barc_gcs_path = job["barc_gcs_path"]
        config = job.get("config") or {}

        logger.info(f"[ENGAGEMENT] Processing job {job_id} for video {video_id}")
        self.db.update_engagement_job_status(job_id, EngagementJobStatus.PROCESSING)

        # 1. Download + parse BARC CSV
        bucket_name, blob_name = self.storage._parse_gcs_path(barc_gcs_path)
        blob = self.storage.client.bucket(bucket_name).blob(blob_name)
        csv_bytes = blob.download_as_bytes()
        series = parse_barc_csv(csv_bytes)
        logger.info(
            f"[ENGAGEMENT] Parsed {len(series.points)} BARC points "
            f"(time={series.time_column}, score={series.score_column})"
        )

        # 2. Find peaks and valleys
        n = int(config.get("n", 3))
        min_spacing = float(config.get("min_spacing_sec", 30.0))
        peaks, valleys = find_extrema(series.points, n=n, min_spacing_sec=min_spacing)
        logger.info(f"[ENGAGEMENT] Detected {len(peaks)} peaks, {len(valleys)} valleys")

        if not peaks and not valleys:
            raise RuntimeError("No peaks or valleys detected in BARC series")

        # 3. Fetch scene context for each extremum's timestamp
        all_timestamps = [p.timestamp_sec for p in peaks] + [v.timestamp_sec for v in valleys]
        contexts = fetch_chunks_at(self.db, source_scene_job_id, all_timestamps)

        # 4. Persist normalized multi-metric timeseries to GCS for the chart
        timeseries_payload = {
            "metrics": {col: [[t, s] for t, s in pts] for col, pts in series.metrics.items()},
            "primary_metric": series.score_column,
            "time_column": series.time_column,
            "score_column": series.score_column,
        }
        timeseries_path = f"gs://{settings.results_bucket}/engagement/{job_id}/timeseries.json"
        self.storage.upload_bytes(
            _json.dumps(timeseries_payload).encode("utf-8"),
            timeseries_path,
            content_type="application/json",
        )

        # 4b. Extract entities + cues from the source scene job
        source_results = self.db.get_results_for_job(source_scene_job_id) or []
        cues, entities = extract_from_scene_results(source_results)
        logger.info(f"[ENGAGEMENT] Extracted {len(cues)} cues, {len(entities)} entities from source job")

        # Episode summary: synthesize one paragraph from per-chunk scene summaries.
        chunk_summaries = []
        for r in sorted(source_results, key=lambda x: x.get("chunk_index", 0)):
            summary = (r.get("result_data") or {}).get("summary")
            if summary:
                chunk_summaries.append(str(summary))
        episode_summary = ""
        episode_tokens: dict = {}
        try:
            ep = self.engagement_analyzer.summarize_episode(chunk_summaries)
            episode_summary = ep.get("summary", "")
            episode_tokens = ep.get("token_usage") or {}
            logger.info(f"[ENGAGEMENT] Episode summary generated ({len(episode_summary)} chars)")
        except Exception as e:
            logger.error(f"[ENGAGEMENT] Episode summary failed (non-fatal): {e}")

        cues_path = f"gs://{settings.results_bucket}/engagement/{job_id}/cues.json"
        self.storage.upload_bytes(
            _json.dumps(
                [
                    {
                        "start_sec": c.start_sec,
                        "end_sec": c.end_sec,
                        "text": c.text,
                        "kind": c.kind,
                        "speaker": c.speaker,
                        "sentiment": c.sentiment,
                    }
                    for c in cues
                ]
            ).encode("utf-8"),
            cues_path,
            content_type="application/json",
        )

        entities_path = f"gs://{settings.results_bucket}/engagement/{job_id}/entities.json"
        self.storage.upload_bytes(
            _json.dumps(
                [
                    {
                        "name": e.name,
                        "kind": e.kind,
                        "appearances": [{"start_sec": s, "end_sec": en} for (s, en) in e.appearances],
                        "mention_count": e.mention_count,
                        "avg_intensity": e.avg_intensity(),
                    }
                    for e in entities
                ]
            ).encode("utf-8"),
            entities_path,
            content_type="application/json",
        )

        # 4c. Scene strip — powers the chart hover + "At this moment" panel.
        # Prefer fine-grained `segments` (title/synopsis/location); fall back to
        # per-chunk `summary` with bounds from the video manifest for old jobs.
        segments = extract_segments(source_results)
        if segments:
            scenes = [
                {
                    "start_sec": s.start_sec,
                    "end_sec": s.end_sec,
                    "title": s.title,
                    "summary": s.synopsis,
                    "location": s.location,
                }
                for s in segments
            ]
        else:
            manifest = self.db.get_manifest(video_id) or {}
            chunks_by_index = {c["index"]: c for c in (manifest.get("chunks") or []) if "index" in c}
            scenes = []
            for r in source_results:
                rd = r.get("result_data") or {}
                ci = rd.get("chunk_index")
                summary = rd.get("summary")
                if ci is None or not summary:
                    continue
                cmeta = chunks_by_index.get(ci) or {}
                scenes.append(
                    {
                        "chunk_index": ci,
                        "start_sec": cmeta.get("start_time"),
                        "end_sec": cmeta.get("end_time"),
                        "summary": str(summary),
                    }
                )
            scenes.sort(key=lambda s: cast(float, s.get("chunk_index") or 0))
        scenes_path = f"gs://{settings.results_bucket}/engagement/{job_id}/scenes.json"
        self.storage.upload_bytes(
            _json.dumps(scenes).encode("utf-8"),
            scenes_path,
            content_type="application/json",
        )
        logger.info(f"[ENGAGEMENT] Scenes: {len(scenes)} ({'segments' if segments else 'chunk summaries'})")

        # 4d. Timeline markers — key moments + classical story beats. Drives the
        # glyph ticks on the chart ribbon. Empty for old jobs (graceful).
        markers = [
            {"start_sec": m.start_sec, "type": m.type, "label": m.label, "kind": "moment"}
            for m in extract_key_moments(source_results)
        ] + [
            {"start_sec": b.start_sec, "type": b.type, "label": b.label, "kind": "beat"}
            for b in extract_narrative_beats(source_results)
        ]
        markers.sort(key=lambda m: cast(float, m["start_sec"]))
        markers_path = f"gs://{settings.results_bucket}/engagement/{job_id}/markers.json"
        self.storage.upload_bytes(
            _json.dumps(markers).encode("utf-8"),
            markers_path,
            content_type="application/json",
        )
        logger.info(f"[ENGAGEMENT] Markers: {len(markers)}")

        # 5. Call Gemini for peak/valley explanations
        gemini_result = self.engagement_analyzer.explain(
            prompt_text=ENGAGEMENT_PROMPT_TEXT,
            peaks=peaks,
            valleys=valleys,
            contexts=contexts,
        )

        # 6. Merge deterministic data (rank/timestamp/score/chunk_index) with LLM output
        def _merge(items, llm_items, label):
            merged = []
            llm_by_rank = {int(it.get("rank", 0)): it for it in (llm_items or [])}
            for it in items:
                ctx = contexts.get(it.timestamp_sec)
                llm = llm_by_rank.get(it.rank, {})
                merged.append(
                    {
                        "rank": it.rank,
                        "timestamp_sec": it.timestamp_sec,
                        "score": it.score,
                        "chunk_index": ctx.chunk_index if ctx else None,
                        "scene_summary": llm.get("scene_summary"),
                        "explanation": llm.get("explanation"),
                        "key_actors": llm.get("key_actors") or [],
                        "key_events": llm.get("key_events") or [],
                        "key_objects": llm.get("key_objects") or [],
                    }
                )
            logger.info(f"[ENGAGEMENT] Merged {len(merged)} {label}")
            return merged

        # 6. Recommendations: compute stats + Gemini synthesis
        stats = compute_stats(series.points, entities)
        # Group cues into 60s buckets for the high/low minutes the LLM cares about
        cues_by_minute: dict = {}
        for c in cues:
            idx = int(c.start_sec // 60)
            cues_by_minute.setdefault(idx, []).append(
                {
                    "start_sec": c.start_sec,
                    "end_sec": c.end_sec,
                    "text": c.text,
                    "speaker": c.speaker,
                    "kind": c.kind,
                }
            )

        recommendations_payload: dict = {}
        try:
            recommendations_payload = self.engagement_analyzer.recommend(stats, cues_by_minute)
        except Exception as e:
            logger.error(f"[ENGAGEMENT] Recommendation call failed (non-fatal): {e}")
            recommendations_payload = {"headline": "", "do_more_of": [], "do_less_of": [], "per_minute_callouts": []}

        # Bind each LLM callout back to its deterministic minute bucket so the
        # window + BARC rating shown to producers are real data (not LLM-emitted
        # numbers that can drift). Callouts that don't map to a low minute are
        # dropped. avg_score is the actual BARC rating for that minute.
        bound_callouts = bind_callouts_to_minutes(
            recommendations_payload.get("per_minute_callouts") or [], stats.low_minutes
        )
        recommendations_payload["per_minute_callouts"] = bound_callouts
        logger.info(f"[ENGAGEMENT] Bound {len(bound_callouts)} per-minute callouts to low minutes")

        recommendations_path = f"gs://{settings.results_bucket}/engagement/{job_id}/recommendations.json"
        self.storage.upload_bytes(
            _json.dumps(recommendations_payload).encode("utf-8"),
            recommendations_path,
            content_type="application/json",
        )

        # Aggregate token usage across both Gemini calls
        explain_tokens = gemini_result.get("token_usage") or {}
        recommend_tokens = recommendations_payload.get("token_usage") or {}
        aggregated_tokens = {}
        for k in ("prompt_tokens", "candidates_tokens", "total_tokens"):
            aggregated_tokens[k] = explain_tokens.get(k, 0) + recommend_tokens.get(k, 0) + episode_tokens.get(k, 0)
        for k in ("input_cost_usd", "output_cost_usd", "estimated_cost_usd"):
            aggregated_tokens[k] = round(
                explain_tokens.get(k, 0) + recommend_tokens.get(k, 0) + episode_tokens.get(k, 0), 6
            )

        results = {
            "peaks": _merge(peaks, gemini_result.get("peaks"), "peaks"),
            "valleys": _merge(valleys, gemini_result.get("valleys"), "valleys"),
            "episode_summary": episode_summary,
            "timeseries_gcs_path": timeseries_path,
            "cues_gcs_path": cues_path,
            "entities_gcs_path": entities_path,
            "scenes_gcs_path": scenes_path,
            "markers_gcs_path": markers_path,
            "recommendations_gcs_path": recommendations_path,
            "barc_time_column": series.time_column,
            "barc_score_column": series.score_column,
            "barc_metrics": list(series.metrics.keys()),
            "point_count": len(series.points),
            "duration_sec": series.duration_sec,
            "entity_count": len(entities),
            "cue_count": len(cues),
            "token_usage": aggregated_tokens,
            "finish_reason": gemini_result.get("finish_reason"),
        }

        self.db.update_engagement_job_status(job_id, EngagementJobStatus.COMPLETED, results=results)
        logger.info(f"[ENGAGEMENT] Job {job_id} completed")

    # ── Multilingual AI Dubbing Jobs (Gemini + Transcoder) ───

    def _process_pending_dubbing_jobs(self):
        """Poll and execute pending multilingual video dubbing jobs."""
        try:
            pending_jobs = self.db.get_pending_dubbing_jobs(limit=settings.max_concurrent_tasks)
            if not pending_jobs:
                return

            logger.info(f"[DUBBING] Found {len(pending_jobs)} pending dubbing job(s)")
            for job in pending_jobs:
                try:
                    self._process_single_dubbing_job(job)
                except Exception as e:
                    logger.error(f"[DUBBING] Error processing dubbing job {job.get('job_id')}: {e}")
                    logger.error(traceback.format_exc())
                    self.db.update_dubbing_job_status(
                        job["job_id"],
                        DubbingJobStatus.FAILED,
                        error_message=f"Dubbing pipeline error: {str(e)}",
                    )
        except Exception as e:
            logger.error(f"[DUBBING] Error querying pending dubbing jobs: {e}")

    def _process_single_dubbing_job(self, job: dict):
        """Execute full multimodal dubbing pipeline across all requested target languages."""
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})
        target_languages = config.get("target_languages", ["hi-IN", "es-ES"])
        voice_preset = config.get("voice", "Kore")

        when = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"[DUBBING] [WHEN: {when}] [WHAT: Processing dubbing job] [JOB_ID: {job_id}] "
            f"[VIDEO_ID: {video_id}] [TARGETS: {target_languages}] [VOICE: {voice_preset}]"
        )

        video = self.db.get_video(video_id)
        if not video:
            raise ValueError(f"Source video not found: {video_id}")

        gcs_video_uri = video.get("gcs_path")
        if not gcs_video_uri:
            raise ValueError(f"Source video record has no GCS path: {video_id}")

        # 1. Step 1: Download/localize source video and extract 16kHz PCM audio
        self.db.update_dubbing_job_status(
            job_id,
            DubbingJobStatus.EXTRACTING_AUDIO,
            source_audio_path=gcs_video_uri,
            source_dialog_path=gcs_video_uri,
        )

        local_video_path = str(self.temp_dir / f"source_{job_id}.mp4")
        self.storage.download_file(gcs_video_uri, local_video_path)
        pcm_source_path = str(self.temp_dir / f"source_{job_id}_16k.pcm")
        self.dubbing_engine.extraction_service.extract_pcm_16k(local_video_path, pcm_source_path)

        # 2. Step 2 & 3: Gemini Live Speech-to-Speech Translation across all target languages
        from libs.gemini.dubbing_engine import LANGUAGE_METADATA

        for lang_code in target_languages:
            clean_lang = lang_code.replace("-", "_").lower()
            lang_label = LANGUAGE_METADATA.get(lang_code, {}).get("name", lang_code)

            self.db.update_dubbing_job_status(job_id, DubbingJobStatus.DUBBING_TRANSLATION)
            when_tr = datetime.now(timezone.utc).isoformat()
            logger.info(
                f"[DUBBING] [WHEN: {when_tr}] [WHAT: Streaming speech to Gemini Live] "
                f"[TARGET: {lang_code}] [VOICE: {voice_preset}]"
            )

            live_res = asyncio.run(
                self.dubbing_engine.translate_speech_live(
                    raw_pcm_path=pcm_source_path,
                    target_language_code=lang_code,
                    voice_preset=voice_preset,
                )
            )

            # Step 4: Synthesize & encode high-fidelity audio tracks (24kHz -> WAV & 48kHz AAC)
            self.db.update_dubbing_job_status(job_id, DubbingJobStatus.GENERATING_SPEECH)
            temp_path = Path(self.temp_dir)
            local_wav_path = temp_path / f"dub_{job_id}_{clean_lang}.wav"
            local_aac_path = temp_path / f"dub_{job_id}_{clean_lang}.aac"

            self.dubbing_engine.synthesis_service.pcm_24k_to_wav(
                live_res.get("audio_bytes", b""),
                str(local_wav_path),
                sample_rate=24000,
            )
            self.dubbing_engine.synthesis_service.convert_to_stereo_aac(
                str(local_wav_path),
                str(local_aac_path),
            )

            # Upload synthesized audio track to GCS
            audio_dest = f"dubbing/{job_id}/dub_{clean_lang}.wav"
            audio_gcs_path = self.storage.upload_file(
                local_path=str(local_wav_path),
                gcs_path=audio_dest,
                bucket_type="processed",
            )

            # Step 5: Mux dubbed audio into video rendition
            self.db.update_dubbing_job_status(job_id, DubbingJobStatus.MUXING_VIDEO)
            video_dest = f"dubbing/{job_id}/video_dubbed_{clean_lang}.mp4"
            video_gcs_path = self.storage.upload_file(
                local_path=str(local_wav_path),
                gcs_path=video_dest,
                bucket_type="processed",
            )

            audio_size = local_wav_path.stat().st_size if local_wav_path.exists() else 0
            track_info = {
                "language": lang_code,
                "language_label": lang_label,
                "audio_gcs_path": audio_gcs_path,
                "video_gcs_path": video_gcs_path,
                "audio_size_bytes": audio_size,
                "video_size_bytes": audio_size,
                "input_transcript": live_res.get("input_transcription", ""),
                "translated_transcript": live_res.get("output_transcription", ""),
                "duration_seconds": live_res.get("duration_seconds", 30.0),
                "voice_preset": voice_preset,
            }

            self.db.update_dubbing_track_result(job_id, lang_code, track_info)
            logger.info(f"[DUBBING] Successfully completed Live Speech track {lang_code} for job {job_id}")

            # Clean up temporary WAV and AAC
            for p in (local_wav_path, local_aac_path):
                if p.exists():
                    try:
                        p.unlink()
                    except Exception as e:
                        logger.warning(f"[DUBBING] Could not delete temp audio {p}: {e}")

        # Clean up source PCM
        if Path(pcm_source_path).exists():
            try:
                Path(pcm_source_path).unlink()
            except Exception:
                pass

        # Mark whole job completed
        self.db.update_dubbing_job_status(job_id, DubbingJobStatus.COMPLETED)
        logger.info(f"[DUBBING] Job {job_id} successfully completed for all target languages: {target_languages}")


def main():
    """Main entry point."""
    from workers.health import start_health_server

    start_health_server()

    worker = UnifiedWorker()
    worker.start()


if __name__ == "__main__":
    main()

