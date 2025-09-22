import os
import ffmpeg
import sys
import shutil
from .models import AudioExtractionResult, ExtractedTrack, ExtractedChannel

class AudioExtractionError(Exception):
    pass

def _is_ffmpeg_installed():
    """Check if ffmpeg is installed and in the system's PATH."""
    return shutil.which("ffmpeg") is not None

def extract_audio(video_file_path: str, output_directory: str = None) -> dict:
    """
    Extracts all audio streams and their individual channels from a video file.
    """
    if not _is_ffmpeg_installed():
        raise AudioExtractionError("ffmpeg is not installed or not found in the system's PATH. Please install ffmpeg to use this feature.")

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
    total_channels_extracted = 0

    for stream in audio_streams:
        track_index = stream['index']
        channels = stream.get('channels', 1)
        channel_layout = stream.get('channel_layout', 'mono' if channels == 1 else 'unknown')
        
        extracted_channels = []

        # Define a list of common channel layouts for ffmpeg's pan filter
        # This is a simplified mapping. For more complex layouts, a more robust solution is needed.
        channel_names = []
        if channel_layout == 'stereo':
            channel_names = ['FL', 'FR']
        elif channel_layout == '5.1':
            channel_names = ['FL', 'FR', 'FC', 'LFE', 'BL', 'BR']
        else:
            # Generic naming for unknown layouts
            channel_names = [f'c{i}' for i in range(channels)]


        if channels > 1:
            # Extract each channel from a multi-channel stream
            for i in range(channels):
                channel_name = channel_names[i] if i < len(channel_names) else f'c{i}'
                output_path = os.path.join(output_directory, f"{base_filename}_track-{track_index}_{channel_name}.flac")
                
                try:
                    # Set the audio filter (`af`) directly in the output.
                    # This avoids the complex escaping issues with the .filter() method.
                    # The pan filter string "mono|c0=c{i}" selects a single channel.
                    audio_filter = f"pan=mono|c0=c{i}"

                    (
                        ffmpeg
                        .input(video_file_path)
                        .output(output_path, map=f"0:{track_index}", acodec='flac', af=audio_filter)
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                    extracted_channels.append(ExtractedChannel(channel_index=i, output_path=output_path))
                    total_channels_extracted += 1
                except ffmpeg.Error as e:
                    raise AudioExtractionError(f"Failed to extract channel {i} from track {track_index}: {e.stderr.decode()}")

        else:
            # Handle mono streams as before
            output_path = os.path.join(output_directory, f"{base_filename}_track-{track_index}_mono.flac")
            try:
                (
                    ffmpeg
                    .input(video_file_path)
                    .output(output_path, map=f"0:{track_index}", acodec='flac')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                extracted_channels.append(ExtractedChannel(channel_index=0, output_path=output_path))
                total_channels_extracted += 1
            except ffmpeg.Error as e:
                raise AudioExtractionError(f"Failed to extract mono track {track_index}: {e.stderr.decode()}")

        individual_tracks.append(ExtractedTrack(
            track_index=track_index,
            channels=channels,
            channel_layout=channel_layout,
            extracted_channels=extracted_channels
        ))

    num_tracks = len(individual_tracks)
    message = (
        f"Successfully extracted {total_channels_extracted} audio channel(s) from {num_tracks} track(s)."
    )

    result = AudioExtractionResult(
        input_video_path=video_file_path,
        individual_tracks=individual_tracks,
        status="success",
        message=message
    )

    return result.dict()
