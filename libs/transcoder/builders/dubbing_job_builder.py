"""Build Transcoder API and FFmpeg multiplexing configs for dubbed video generation."""

import logging
from typing import Dict, List, Optional
from google.cloud.video.transcoder_v1 import types as transcoder_types

logger = logging.getLogger(__name__)


def build_dubbing_mux_job_config(
    video_input_gcs_uri: str,
    dubbed_audio_gcs_uri: str,
    output_gcs_prefix: str,
    language_code: str,
    resolution_height: int = 720,
    video_bitrate_bps: int = 3_000_000,
    audio_bitrate_bps: int = 128_000,
) -> transcoder_types.Job:
    """Build a Transcoder Job proto that muxes a source video with a synthesized dubbed audio track.

    Args:
        video_input_gcs_uri: GCS path to original source video stream (e.g. gs://bucket/video.mp4).
        dubbed_audio_gcs_uri: GCS path to synthesized target language audio (e.g. gs://bucket/dub_hi.wav).
        output_gcs_prefix: GCS directory for rendered output.
        language_code: Target language code for track naming.
        resolution_height: Output height in pixels (e.g. 720, 1080).
        video_bitrate_bps: Video stream bitrate in bps.
        audio_bitrate_bps: Audio stream bitrate in bps.

    Returns:
        Transcoder Job protobuf instance.
    """
    clean_lang = language_code.replace("-", "_").lower()
    logger.info(
        f"[DubbingJobBuilder] Building mux config: video={video_input_gcs_uri}, audio={dubbed_audio_gcs_uri}, "
        f"lang={language_code}, prefix={output_gcs_prefix}"
    )

    inputs = [
        transcoder_types.Input(key="video_source", uri=video_input_gcs_uri),
        transcoder_types.Input(key="dubbed_audio", uri=dubbed_audio_gcs_uri),
    ]

    elementary_streams = [
        transcoder_types.ElementaryStream(
            key="video-stream0",
            video_stream=transcoder_types.VideoStream(
                h264=transcoder_types.VideoStream.H264CodecSettings(
                    height_pixels=resolution_height,
                    bitrate_bps=video_bitrate_bps,
                    frame_rate=30,
                    profile="high",
                )
            ),
        ),
        transcoder_types.ElementaryStream(
            key="audio-stream0",
            audio_stream=transcoder_types.AudioStream(
                codec="aac",
                bitrate_bps=audio_bitrate_bps,
                channel_count=2,
                channel_layout=["fl", "fr"],
                sample_rate_hertz=48000,
            ),
        ),
    ]

    mux_streams = [
        transcoder_types.MuxStream(
            key=f"dubbed_mux_{clean_lang}",
            container="mp4",
            elementary_streams=["video-stream0", "audio-stream0"],
            file_name=f"video_dubbed_{clean_lang}.mp4",
        )
    ]

    job_config = transcoder_types.JobConfig(
        inputs=inputs,
        elementary_streams=elementary_streams,
        mux_streams=mux_streams,
        output=transcoder_types.Output(uri=output_gcs_prefix),
    )

    return transcoder_types.Job(
        input_uri=video_input_gcs_uri,
        output_uri=output_gcs_prefix,
        config=job_config,
    )
