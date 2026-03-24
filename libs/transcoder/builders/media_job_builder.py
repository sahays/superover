"""Build Transcoder API protobuf config for media compression/audio extraction."""

from google.cloud.video.transcoder_v1 import types as transcoder_types
from libs.transcoder.config_mapping import (
    get_target_height,
    crf_to_bitrate,
    get_audio_codec,
    get_audio_bitrate_bps,
)


def build_media_job_config(
    input_gcs_uri: str,
    output_gcs_prefix: str,
    compress: bool = True,
    resolution: str = "480p",
    crf: int = 23,
    extract_audio: bool = True,
    audio_format: str = "aac",
    audio_bitrate: str = "128k",
    dialog_mode: bool = False,
) -> transcoder_types.Job:
    """Build a Transcoder Job proto for media compression + audio extraction.

    Args:
        dialog_mode: If True, extracts dialog-optimized mono audio (1 channel,
            center channel, 16kHz sample rate). Skips video compression.
    """
    elementary_streams = []
    mux_streams = []

    if compress and not dialog_mode:
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

    if extract_audio or dialog_mode:
        audio_codec = get_audio_codec(audio_format)
        audio_bps = get_audio_bitrate_bps(audio_bitrate)

        if dialog_mode:
            # Dialog mode: mono center channel, 16kHz, speech-optimized
            channel_count = 1
            channel_layout = ["fc"]
            sample_rate = 16000
        else:
            channel_count = 2
            channel_layout = ["fl", "fr"]
            sample_rate = 48000

        elementary_streams.append(
            transcoder_types.ElementaryStream(
                key="audio-stream0",
                audio_stream=transcoder_types.AudioStream(
                    codec=audio_codec,
                    bitrate_bps=audio_bps,
                    channel_count=channel_count,
                    channel_layout=channel_layout,
                    sample_rate_hertz=sample_rate,
                ),
            )
        )

        file_label = "media_dialog" if dialog_mode else "media_audio"
        audio_ext = "m4a" if audio_format == "aac" else audio_format
        audio_container = "mp4" if audio_format == "aac" else audio_format
        mux_streams.append(
            transcoder_types.MuxStream(
                key="audio-mux",
                container=audio_container,
                elementary_streams=["audio-stream0"],
                file_name=f"{file_label}.{audio_ext}",
            )
        )

    job_config = transcoder_types.JobConfig(
        inputs=[transcoder_types.Input(key="input0", uri=input_gcs_uri)],
        elementary_streams=elementary_streams,
        mux_streams=mux_streams,
        output=transcoder_types.Output(uri=output_gcs_prefix),
    )

    return transcoder_types.Job(
        input_uri=input_gcs_uri,
        output_uri=output_gcs_prefix,
        config=job_config,
    )
