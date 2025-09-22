import os
import ffmpeg
import shutil
import logging
import tempfile
from .models import AudioExtractionResult, ExtractedTrack, ExtractedChannel
from common.storage import StorageManager

class AudioExtractionError(Exception):
    pass

def _is_ffmpeg_installed():
    return shutil.which("ffmpeg") is not None

def extract_audio(video_file_path: str, output_directory: str) -> dict:
    """
    Extracts audio channels from a video file (local or GCS) and saves them to GCS.
    """
    if not _is_ffmpeg_installed():
        raise AudioExtractionError("ffmpeg is not installed or not found in the system's PATH.")

    storage = StorageManager()
    
    with tempfile.TemporaryDirectory() as local_temp_dir:
        # 1. Get a local copy of the source video
        local_video_path = storage.get_local_path(video_file_path)
        base_filename = os.path.splitext(os.path.basename(local_video_path))[0]

        # 2. Probe the local video file
        try:
            probe = ffmpeg.probe(local_video_path)
        except ffmpeg.Error as e:
            raise AudioExtractionError(f"Failed to probe file: {e.stderr.decode()}")

        audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
        if not audio_streams:
            raise AudioExtractionError("No audio streams found in the video file.")

        # 3. Process and upload each stream
        individual_tracks = []
        total_channels_extracted = 0
        
        for stream in audio_streams:
            track_index = stream['index']
            channels = stream.get('channels', 1)
            channel_layout = stream.get('channel_layout', 'mono' if channels == 1 else 'unknown')
            extracted_channels = []

            if channels > 1:
                for i in range(channels):
                    channel_name = f'c{i}'
                    local_output_path = os.path.join(local_temp_dir, f"{base_filename}_track-{track_index}_{channel_name}.flac")
                    
                    try:
                        audio_filter = f"pan=mono|c0=c{i}"
                        ffmpeg.input(local_video_path).output(local_output_path, map=f"0:{track_index}", acodec='flac', af=audio_filter).overwrite_output().run(capture_stdout=True, capture_stderr=True)
                        
                        gcs_path = os.path.join(output_directory, os.path.basename(local_output_path))
                        storage.move_file(local_output_path, gcs_path)
                        
                        extracted_channels.append(ExtractedChannel(channel_index=i, output_path=gcs_path))
                        total_channels_extracted += 1
                    except ffmpeg.Error as e:
                        logging.error(f"Failed to extract channel {i} from track {track_index}: {e.stderr.decode()}")
            else: # Mono stream
                local_output_path = os.path.join(local_temp_dir, f"{base_filename}_track-{track_index}_mono.flac")
                try:
                    ffmpeg.input(local_video_path).output(local_output_path, map=f"0:{track_index}", acodec='flac').overwrite_output().run(capture_stdout=True, capture_stderr=True)
                    
                    gcs_path = os.path.join(output_directory, os.path.basename(local_output_path))
                    storage.move_file(local_output_path, gcs_path)

                    extracted_channels.append(ExtractedChannel(channel_index=0, output_path=gcs_path))
                    total_channels_extracted += 1
                except ffmpeg.Error as e:
                    logging.error(f"Failed to extract mono track {track_index}: {e.stderr.decode()}")

            individual_tracks.append(ExtractedTrack(track_index=track_index, channels=channels, channel_layout=channel_layout, extracted_channels=extracted_channels))

    storage.cleanup_temp_files()

    message = f"Successfully extracted {total_channels_extracted} audio channel(s) from {len(individual_tracks)} track(s)."
    result = AudioExtractionResult(
        input_video_path=video_file_path,
        individual_tracks=individual_tracks,
        status="success",
        message=message
    )
    return result.dict()