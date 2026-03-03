"""Scene analysis orchestration — chunking via Transcoder + analysis via SceneProcessor."""

import logging
from pathlib import Path
from typing import Dict, Any, List

from config import settings
from libs.database import get_db, SceneJobStatus

logger = logging.getLogger(__name__)


class SceneOrchestrator:
    """Orchestrates the full scene analysis pipeline: chunking then analysis."""

    def __init__(self, transcoder, scene_processor):
        self.transcoder = transcoder
        self.scene_processor = scene_processor

    def run(self, job: Dict[str, Any]) -> None:
        """Execute chunking + analysis for a scene job.

        Assumes the job is already in PROCESSING state.
        """
        db = get_db()
        job_id = job["job_id"]
        video_id = job["video_id"]
        config = job.get("config", {})

        compressed_video_path = config.get("compressed_video_path")
        chunk_duration = config.get("chunk_duration", 30)
        should_chunk = config.get("chunk", True)
        context_items = config.get("context_items", [])

        # Get video info
        video = db.get_video(video_id)
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
        chunks = self._resolve_chunks(
            db,
            job_id,
            video_id,
            video,
            video_path_to_process,
            should_chunk,
            chunk_duration,
            manifest_data,
        )

        db.create_manifest(video_id, manifest_data)

        # Analysis
        db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "analyzing"})
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
        self._finalize_job(db, job_id, chunks)

    def _resolve_chunks(
        self,
        db,
        job_id: str,
        video_id: str,
        video: Dict[str, Any],
        video_path_to_process: str,
        should_chunk: bool,
        chunk_duration: int,
        manifest_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Determine chunks — either via Transcoder API or as a single whole-file chunk."""
        if should_chunk and chunk_duration > 0:
            db.update_scene_job_status(job_id, SceneJobStatus.PROCESSING, results={"step": "chunking"})

            total_duration = video.get("metadata", {}).get("duration")
            if not total_duration:
                logger.warning(
                    f"Video {video_id} has no duration metadata. "
                    f"Falling back to no-chunking mode (processing entire video as single chunk)."
                )
                chunks = [
                    {
                        "index": 0,
                        "filename": Path(video_path_to_process).name,
                        "gcs_path": video_path_to_process,
                        "duration": 0,
                    }
                ]
            else:
                output_prefix = f"gs://{settings.processed_bucket}/{video_id}/scene_chunks/"
                transcoder_job_name = self.transcoder.submit_chunking_job(
                    input_gcs_uri=video_path_to_process,
                    output_gcs_prefix=output_prefix,
                    chunk_duration=chunk_duration,
                    total_duration=total_duration,
                )
                status = self.transcoder.wait_for_completion(transcoder_job_name)
                if status["state"] != "SUCCEEDED":
                    raise Exception(f"Chunking failed: {status.get('error', 'Unknown error')}")
                chunks = self.transcoder.build_chunk_list(output_prefix, chunk_duration, total_duration)
        else:
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
        return chunks

    @staticmethod
    def _finalize_job(db, job_id: str, chunks: List[Dict[str, Any]]) -> None:
        """Aggregate results and mark job as completed."""
        job_results = db.get_results_for_job(job_id)
        total_tokens = 0
        total_cost = 0.0
        last_stop_reason = "completed"

        for res in job_results:
            usage = res.get("result_data", {}).get("token_usage", {})
            total_tokens += usage.get("total_tokens", 0)
            total_cost += usage.get("estimated_cost_usd", 0.0)
            last_stop_reason = res.get("result_data", {}).get("finish_reason", last_stop_reason)

        db.update_scene_job_status(
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
