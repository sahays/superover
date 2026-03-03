"""
Transcoder API client for media processing.
Replaces local FFmpeg operations with cloud-based transcoding.
"""

import logging
import time
from typing import Dict, Any, List

from google.cloud.video import transcoder_v1
from google.cloud.video.transcoder_v1 import types as transcoder_types
from config import settings
from .builders import build_media_job_config, build_chunking_job_config

logger = logging.getLogger(__name__)


class TranscoderClient:
    """Wraps the Transcoder API for media processing jobs."""

    def __init__(self):
        """Initialize the Transcoder API client."""
        self.client = transcoder_v1.TranscoderServiceClient()
        self.project_id = settings.gcp_project_id
        self.location = settings.transcoder_location
        self.parent = f"projects/{self.project_id}/locations/{self.location}"

    def submit_media_job(
        self,
        input_gcs_uri: str,
        output_gcs_prefix: str,
        compress: bool = True,
        resolution: str = "480p",
        crf: int = 23,
        extract_audio: bool = True,
        audio_format: str = "aac",
        audio_bitrate: str = "128k",
    ) -> str:
        """
        Submit a media processing job (compression + optional audio extraction).

        Returns:
            Transcoder job name (projects/.../locations/.../jobs/...)
        """
        job = build_media_job_config(
            input_gcs_uri=input_gcs_uri,
            output_gcs_prefix=output_gcs_prefix,
            compress=compress,
            resolution=resolution,
            crf=crf,
            extract_audio=extract_audio,
            audio_format=audio_format,
            audio_bitrate=audio_bitrate,
        )

        response = self.client.create_job(parent=self.parent, job=job)
        logger.info(f"Submitted media transcoder job: {response.name}")
        return response.name

    def submit_chunking_job(
        self,
        input_gcs_uri: str,
        output_gcs_prefix: str,
        chunk_duration: int,
        total_duration: float,
    ) -> str:
        """
        Submit a video chunking job using EditAtom segments.

        Returns:
            Transcoder job name
        """
        job = build_chunking_job_config(
            input_gcs_uri=input_gcs_uri,
            output_gcs_prefix=output_gcs_prefix,
            chunk_duration=chunk_duration,
            total_duration=total_duration,
        )

        response = self.client.create_job(parent=self.parent, job=job)
        logger.info(f"Submitted chunking transcoder job: {response.name}")
        return response.name

    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """Get the status of a Transcoder job."""
        job = self.client.get_job(name=job_name)

        state_map = {
            transcoder_types.Job.ProcessingState.PROCESSING_STATE_UNSPECIFIED: "UNSPECIFIED",
            transcoder_types.Job.ProcessingState.PENDING: "PENDING",
            transcoder_types.Job.ProcessingState.RUNNING: "RUNNING",
            transcoder_types.Job.ProcessingState.SUCCEEDED: "SUCCEEDED",
            transcoder_types.Job.ProcessingState.FAILED: "FAILED",
        }

        state = state_map.get(job.state, "UNKNOWN")

        result = {
            "state": state,
            "error": None,
            "output_uri": job.config.output.uri if job.config and job.config.output else job.output_uri,
        }

        if job.state == transcoder_types.Job.ProcessingState.FAILED:
            result["error"] = str(job.error) if job.error else "Unknown transcoder error"

        return result

    def wait_for_completion(
        self,
        job_name: str,
        poll_interval: int = 5,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """Poll a Transcoder job until it completes or fails."""
        if timeout is None:
            timeout = settings.transcoder_job_timeout_seconds

        start_time = time.time()

        while True:
            status = self.get_job_status(job_name)

            if status["state"] == "SUCCEEDED":
                logger.info(f"Transcoder job completed: {job_name}")
                return status

            if status["state"] == "FAILED":
                logger.error(f"Transcoder job failed: {job_name} - {status['error']}")
                return status

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"Transcoder job timed out after {timeout}s: {job_name}")
                return {"state": "TIMEOUT", "error": f"Job timed out after {timeout}s", "output_uri": None}

            logger.info(f"Transcoder job {job_name} state: {status['state']} ({elapsed:.0f}s elapsed)")
            time.sleep(poll_interval)

    def extract_metadata_from_job(self, job_name: str, input_gcs_uri: str = None) -> Dict[str, Any]:
        """Extract metadata from a completed Transcoder job."""
        from libs.storage import get_storage

        job = self.client.get_job(name=job_name)

        metadata: Dict[str, Any] = {
            "duration": None,
            "video": {},
            "audio": {},
        }

        if input_gcs_uri:
            try:
                storage = get_storage()
                storage.get_file_metadata(input_gcs_uri)
            except Exception as e:
                logger.warning(f"Could not get GCS metadata for {input_gcs_uri}: {e}")

        if job.config and job.config.elementary_streams:
            for stream in job.config.elementary_streams:
                if stream.video_stream and stream.video_stream.h264:
                    h264 = stream.video_stream.h264
                    metadata["video"] = {
                        "codec": "h264",
                        "height": h264.height_pixels,
                        "width": h264.width_pixels if h264.width_pixels else None,
                        "bitrate_bps": h264.bitrate_bps,
                        "frame_rate": h264.frame_rate,
                    }
                if stream.audio_stream:
                    audio = stream.audio_stream
                    metadata["audio"] = {
                        "codec": audio.codec,
                        "bitrate_bps": audio.bitrate_bps,
                        "channel_count": audio.channel_count,
                        "sample_rate": audio.sample_rate_hertz,
                    }

        if not metadata["duration"] and metadata.get("video", {}).get("bitrate_bps"):
            try:
                output_uri = job.config.output.uri if job.config and job.config.output else job.output_uri
                compressed_path = f"{output_uri}media_compressed.mp4"
                storage = get_storage()
                file_meta = storage.get_file_metadata(compressed_path)
                file_size_bytes = file_meta.get("size", 0)
                total_bitrate = metadata["video"]["bitrate_bps"]
                audio_bps = metadata.get("audio", {}).get("bitrate_bps", 0)
                total_bitrate += audio_bps
                if total_bitrate > 0 and file_size_bytes > 0:
                    metadata["duration"] = round((file_size_bytes * 8) / total_bitrate, 2)
            except Exception as e:
                logger.warning(f"Could not estimate duration from output: {e}")

        return metadata

    def build_chunk_list(
        self,
        output_gcs_prefix: str,
        chunk_duration: int,
        total_duration: float,
    ) -> List[Dict[str, Any]]:
        """Build the chunk metadata list from expected Transcoder output paths."""
        chunks = []
        start = 0.0
        index = 0

        while start < total_duration:
            end = min(start + chunk_duration, total_duration)
            duration = end - start
            filename = f"chunk_{index:04d}.mp4"
            gcs_path = f"{output_gcs_prefix}{filename}"

            chunks.append(
                {
                    "index": index,
                    "filename": filename,
                    "gcs_path": gcs_path,
                    "start_time": start,
                    "end_time": end,
                    "duration": duration,
                }
            )

            start = end
            index += 1

        return chunks
