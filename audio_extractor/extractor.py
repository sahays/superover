import os
import ffmpeg
import sys
from .models import AudioExtractionResult, ExtractedTrack

class AudioExtractionError(Exception):
    pass

def extract_audio(video_file_path: str, output_directory: str = None) -> dict:
    """
    Extracts all audio streams from a video file, creating both individual
    and combined audio files.
    """
    if not os.path.exists(video_file_path):
        raise FileNotFoundError(f"Input file not found: {video_file_path}")

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)
    else:
        output_directory = os.path.dirname(video_file_path)

    base_filename = os.path.splitext(os.path.basename(video_file_path))[0]

    try:
        probe = ffmpeg.probe(video_file_path)
    except ffmpeg.Error as e:
        raise AudioExtractionError(f"Failed to probe file: {e.stderr.decode() if e.stderr else 'Unknown error'}")

    audio_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'audio']

    if not audio_streams:
        raise AudioExtractionError("No audio streams found in the video file.")

    individual_tracks = []
    stream_specifiers = []

    for stream in audio_streams:
        track_index = stream['index']
        output_path = os.path.join(output_directory, f"{base_filename}_track-{track_index}.flac")
        
        try:
            (
                ffmpeg
                .input(video_file_path)
                .output(output_path, map=f"0:{track_index}", acodec='flac')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            individual_tracks.append(ExtractedTrack(track_index=track_index, output_path=output_path))
            stream_specifiers.append(f"[0:{track_index}]")
        except ffmpeg.Error as e:
            raise AudioExtractionError(f"Failed to extract track {track_index}: {e.stderr.decode()}")

    combined_audio_path = os.path.join(output_directory, f"{base_filename}_combined.flac")
    
    try:
        inp = ffmpeg.input(video_file_path)
        streams_to_mix = [inp[str(s['index'])] for s in audio_streams]

        if len(streams_to_mix) == 1:
            # If there's only one audio stream, no need to mix.
            output_stream = streams_to_mix[0]
        else:
            # Otherwise, mix all audio streams together.
            output_stream = ffmpeg.filter(streams_to_mix, 'amix', inputs=len(streams_to_mix))
        
        (
            output_stream
            .output(combined_audio_path, acodec='flac')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        raise AudioExtractionError(f"Failed to combine audio tracks: {e.stderr.decode()}")

    result = AudioExtractionResult(
        input_video_path=video_file_path,
        combined_audio_path=combined_audio_path,
        individual_tracks=individual_tracks,
        status="success",
        message=f"Extracted {len(individual_tracks)} individual audio tracks and 1 combined track."
    )

    return result.dict()
