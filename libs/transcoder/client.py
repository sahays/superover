"""
Transcoder API client for media processing.
Replaces local FFmpeg operations with cloud-based transcoding.
"""

import logging
import time
from typing import Dict, Any, List, Optional

from google.cloud.video import transcoder_v1
from google.cloud.video.transcoder_v1 import types as transcoder_types
from google.protobuf import duration_pb2
from config import settings
from .config_mapping import (
    get_target_height,
    crf_to_bitrate,
    get_audio_codec,
    get_audio_bitrate_bps,
)

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

        Args:
            input_gcs_uri: GCS URI of the input video (gs://bucket/path)
            output_gcs_prefix: GCS URI prefix for outputs (gs://bucket/prefix/)
            compress: Whether to compress video
            resolution: Target resolution (360p, 480p, etc.)
            crf: CRF value (mapped to bitrate)
            extract_audio: Whether to extract audio
            audio_format: Audio format (aac, mp3, wav)
            audio_bitrate: Audio bitrate string (128k, 192k, etc.)

        Returns:
            Transcoder job name (projects/.../locations/.../jobs/...)
        """
        elementary_streams = []
        mux_streams = []

        if compress:
            # Video stream
            height = get_target_height(resolution)
            bitrate = crf_to_bitrate(crf, resolution)
            elementary_streams.append(
                transcoder_types.ElementaryStream(
                    key="video-stream0",
                    video_stream=transcoder_types.VideoStream(
                        h264=transcoder_types.VideoStream.H264CodecSettings(
                            height_pixels=height,
                            bitrate_bps=bitrate,
                            frame_rate=30,
                            profile="high",
                        )
                    ),
                )
            )
            mux_streams.append(
                transcoder_types.MuxStream(
                    key="video-mux",
                    container="mp4",
                    elementary_streams=["video-stream0", "audio-stream0"] if extract_audio else ["video-stream0"],
                    file_name="media_compressed.mp4",
                )
            )

        if extract_audio:
            # Audio stream
            audio_codec = get_audio_codec(audio_format)
            audio_bps = get_audio_bitrate_bps(audio_bitrate)

            elementary_streams.append(
                transcoder_types.ElementaryStream(
                    key="audio-stream0",
                    audio_stream=transcoder_types.AudioStream(
                        codec=audio_codec,
                        bitrate_bps=audio_bps,
                        channel_count=1,
                        sample_rate_hertz=22050,
                    ),
                )
            )

            # Separate audio-only output (aac is muxed in mp4 container)
            audio_ext = "m4a" if audio_format == "aac" else audio_format
            audio_container = "mp4" if audio_format == "aac" else audio_format
            mux_streams.append(
                transcoder_types.MuxStream(
                    key="audio-mux",
                    container=audio_container,
                    elementary_streams=["audio-stream0"],
                    file_name=f"media_audio.{audio_ext}",
                )
            )

        job_config = transcoder_types.JobConfig(
            inputs=[transcoder_types.Input(key="input0", uri=input_gcs_uri)],
            elementary_streams=elementary_streams,
            mux_streams=mux_streams,
            output=transcoder_types.Output(uri=output_gcs_prefix),
        )

        job = transcoder_types.Job(
            input_uri=input_gcs_uri,
            output_uri=output_gcs_prefix,
            config=job_config,
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

        Each chunk becomes a separate output file via its own EditAtom + MuxStream.

        Args:
            input_gcs_uri: GCS URI of the input video
            output_gcs_prefix: GCS URI prefix for chunk outputs
            chunk_duration: Duration of each chunk in seconds
            total_duration: Total video duration in seconds

        Returns:
            Transcoder job name
        """
        # Calculate chunk boundaries
        chunks = []
        start = 0.0
        index = 0
        while start < total_duration:
            end = min(start + chunk_duration, total_duration)
            chunks.append({"index": index, "start": start, "end": end})
            start = end
            index += 1

        # Build edit atoms, elementary streams, and mux streams for each chunk
        edit_list = []
        elementary_streams = []
        mux_streams = []

        for chunk in chunks:
            atom_key = f"atom{chunk['index']}"
            video_key = f"video-{chunk['index']}"
            audio_key = f"audio-{chunk['index']}"
            mux_key = f"chunk-{chunk['index']}"

            # EditAtom defines the time segment using protobuf Duration
            start_sec = chunk["start"]
            end_sec = chunk["end"]
            edit_list.append(
                transcoder_types.EditAtom(
                    key=atom_key,
                    inputs=["input0"],
                    start_time_offset=duration_pb2.Duration(
                        seconds=int(start_sec),
                        nanos=int((start_sec % 1) * 1e9),
                    ),
                    end_time_offset=duration_pb2.Duration(
                        seconds=int(end_sec),
                        nanos=int((end_sec % 1) * 1e9),
                    ),
                )
            )

            # Video stream for this chunk (copy codec for speed)
            elementary_streams.append(
                transcoder_types.ElementaryStream(
                    key=video_key,
                    video_stream=transcoder_types.VideoStream(
                        h264=transcoder_types.VideoStream.H264CodecSettings(
                            bitrate_bps=5_000_000,
                            frame_rate=30,
                        )
                    ),
                )
            )

            # Audio stream for this chunk
            elementary_streams.append(
                transcoder_types.ElementaryStream(
                    key=audio_key,
                    audio_stream=transcoder_types.AudioStream(
                        codec="aac",
                        bitrate_bps=128_000,
                    ),
                )
            )

            # MuxStream combining video + audio for this chunk
            mux_streams.append(
                transcoder_types.MuxStream(
                    key=mux_key,
                    container="mp4",
                    elementary_streams=[video_key, audio_key],
                    file_name=f"chunk_{chunk['index']:04d}.mp4",
                )
            )

        job_config = transcoder_types.JobConfig(
            inputs=[transcoder_types.Input(key="input0", uri=input_gcs_uri)],
            edit_list=edit_list,
            elementary_streams=elementary_streams,
            mux_streams=mux_streams,
            output=transcoder_types.Output(uri=output_gcs_prefix),
        )

        job = transcoder_types.Job(
            input_uri=input_gcs_uri,
            output_uri=output_gcs_prefix,
            config=job_config,
        )

        response = self.client.create_job(parent=self.parent, job=job)
        logger.info(f"Submitted chunking transcoder job: {response.name} ({len(chunks)} chunks)")
        return response.name

    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """
        Get the status of a Transcoder job.

        Args:
            job_name: Full job resource name

        Returns:
            Dict with state, error (if any), and output URIs
        """
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
            "output_uri": job.output_uri,
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
        """
        Poll a Transcoder job until it completes or fails.

        Args:
            job_name: Full job resource name
            poll_interval: Seconds between polls
            timeout: Max seconds to wait (default from settings)

        Returns:
            Final job status dict
        """
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
        """
        Extract metadata from a completed Transcoder job.

        Probes the input file via GCS to get source duration/size, and reads the
        job config for output stream settings.

        Args:
            job_name: Full job resource name
            input_gcs_uri: GCS URI of the source file (for duration via GCS metadata)

        Returns:
            Dict with duration, resolution, codec, fps, bitrate info
        """
        from libs.storage import get_storage

        job = self.client.get_job(name=job_name)

        metadata: Dict[str, Any] = {
            "duration": None,
            "video": {},
            "audio": {},
        }

        # Get source file duration from GCS object metadata
        if input_gcs_uri:
            try:
                storage = get_storage()
                file_meta = storage.get_file_metadata(input_gcs_uri)
                # GCS content-type based duration isn't available directly,
                # but size is. Duration must come from the Transcoder job output.
            except Exception as e:
                logger.warning(f"Could not get GCS metadata for {input_gcs_uri}: {e}")

        # The Transcoder API exposes input analysis in the job result after completion.
        # job.config.edit_list atoms contain time offsets that imply duration,
        # and job.output contains mux stream info. However the most reliable
        # duration source is the mux_stream output file durations or the
        # total input duration if the API provides it.
        #
        # For the output stream settings, read from elementary_streams.
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

        # Estimate duration from output file size and bitrate if not set
        if not metadata["duration"] and metadata.get("video", {}).get("bitrate_bps"):
            try:
                # Use compressed output size to estimate duration
                output_uri = job.output_uri
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
        """
        Build the chunk metadata list from expected Transcoder output paths.

        Args:
            output_gcs_prefix: GCS URI prefix where chunks are output
            chunk_duration: Duration of each chunk
            total_duration: Total video duration

        Returns:
            List of chunk dicts with index, filename, gcs_path, duration
        """
        chunks = []
        start = 0.0
        index = 0

        while start < total_duration:
            end = min(start + chunk_duration, total_duration)
            duration = end - start
            filename = f"chunk_{index:04d}.mp4"
            gcs_path = f"{output_gcs_prefix}{filename}"

            chunks.append({
                "index": index,
                "filename": filename,
                "gcs_path": gcs_path,
                "start_time": start,
                "end_time": end,
                "duration": duration,
            })

            start = end
            index += 1

        return chunks
