"""Build Transcoder API protobuf config for video chunking."""

from google.cloud.video.transcoder_v1 import types as transcoder_types
from google.protobuf import duration_pb2


def build_chunking_job_config(
    input_gcs_uri: str,
    output_gcs_prefix: str,
    chunk_duration: int,
    total_duration: float,
) -> transcoder_types.Job:
    """Build a Transcoder Job proto that splits video into chunks via EditAtom segments."""
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

        elementary_streams.append(
            transcoder_types.ElementaryStream(
                key=audio_key,
                audio_stream=transcoder_types.AudioStream(
                    codec="aac",
                    bitrate_bps=128_000,
                ),
            )
        )

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

    return transcoder_types.Job(
        input_uri=input_gcs_uri,
        output_uri=output_gcs_prefix,
        config=job_config,
    )
