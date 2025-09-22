import os
import ffmpeg
import re
import time
import logging
from .models import VideoProcessingResult, ProcessedFile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoProcessingError(Exception):
    pass

RESOLUTION_SHORTHANDS = {
    "360p": "640x360",
    "480p": "854x480",
    "720p": "1280x720",
    "1080p": "1920x1080",
    "1440p": "2560x1440",
    "2k": "2560x1440",
    "2160p": "3840x2160",
    "4k": "3840x2160",
}

def _resolve_resolution(res_string: str) -> str:
    if not res_string:
        return None
    res_string = res_string.lower()
    if res_string in RESOLUTION_SHORTHANDS:
        return RESOLUTION_SHORTHANDS[res_string]
    if re.match(r'^\d+x\d+$', res_string):
        return res_string
    raise VideoProcessingError(f"Invalid resolution format: '{res_string}'. Use shorthand or 'widthxheight'.")

def _run_ffmpeg(stream, **kwargs):
    try:
        logging.info("Starting FFmpeg process...")
        stream.run(capture_stdout=True, capture_stderr=True, **kwargs)
        logging.info("FFmpeg process finished successfully.")
    except ffmpeg.Error as e:
        raise VideoProcessingError(f"FFmpeg error: {e.stderr.decode()}")

def _split_video(input_path, timestamps, output_dir):
    logging.info(f"Splitting video '{input_path}' with timestamps: {timestamps}")
    output_files = []
    try:
        timestamp_pairs = timestamps.split(',')
        for i, pair in enumerate(timestamp_pairs):
            start, end = pair.split('-')
            output_path = os.path.join(output_dir, f"split_{i}_{os.path.basename(input_path)}")
            stream = ffmpeg.input(input_path, ss=start, to=end).output(output_path)
            _run_ffmpeg(stream, overwrite_output=True)
            output_files.append(output_path)
    except Exception as e:
        raise VideoProcessingError(f"Invalid timestamp format: {e}")
    logging.info(f"Finished splitting. Created {len(output_files)} files.")
    return output_files

def _chunk_video(input_path, duration, output_dir):
    logging.info(f"Chunking video '{input_path}' into {duration}-second segments.")
    output_template = os.path.join(output_dir, f"chunk_%03d_{os.path.basename(input_path)}")
    stream = ffmpeg.input(input_path).output(
        output_template,
        map=0,
        f='segment',
        segment_time=duration,
        reset_timestamps=1,
        sc_threshold=0  # Ensure keyframes at segment boundaries
    )
    _run_ffmpeg(stream, overwrite_output=True)
    
    output_files = [os.path.join(output_dir, f) for f in sorted(os.listdir(output_dir)) if f.startswith('chunk_') and f.endswith(os.path.basename(input_path))]
    logging.info(f"Finished chunking. Created {len(output_files)} files.")
    return output_files

def _compress_videos(input_paths, resolution, output_dir):
    logging.info(f"Compressing {len(input_paths)} video file(s) to {resolution}.")
    output_files = []
    width, height = map(int, resolution.split('x'))
    for i, path in enumerate(input_paths):
        base_name = os.path.splitext(os.path.basename(path))[0]
        output_path = os.path.join(output_dir, f"compressed_{i}_{base_name}.mp4")
        
        probe = ffmpeg.probe(path)
        audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
        
        input_stream = ffmpeg.input(path)
        video_stream = input_stream.video.filter('scale', width, height)
        
        if audio_streams:
            audio_stream = input_stream.audio.filter('amix', inputs=len(audio_streams))
            stream = ffmpeg.output(video_stream, audio_stream, output_path, vcodec='libx264', pix_fmt='yuv420p')
        else:
            stream = ffmpeg.output(video_stream, output_path, vcodec='libx264', pix_fmt='yuv420p')

        _run_ffmpeg(stream, overwrite_output=True)
        output_files.append(output_path)
    logging.info("Finished compression.")
    return output_files

import os
import ffmpeg
import re
import time
import logging
import tempfile
from .models import VideoProcessingResult, ProcessedFile
from common.storage import StorageManager

# (Keep logging and RESOLUTION_SHORTHANDS definitions as they are)
# ...

def _run_ffmpeg(stream, **kwargs):
    # ... (This function remains the same)
    
def _chunk_video(input_path, duration, output_dir):
    # ... (This function remains the same, but now `input_path` and `output_dir` are local paths)

# ... (Other helper functions like _split_video and _compress_videos also operate on local paths)

def process_video(**kwargs) -> dict:
    start_time = time.time()
    
    video_file_path = kwargs.get("video_file_path")
    output_directory = kwargs.get("output_directory") # This will be a GCS path
    # ... (other kwargs)

    storage = StorageManager()
    
    # Create a temporary local directory for processing
    with tempfile.TemporaryDirectory() as local_temp_dir:
        # 1. Get a local copy of the source video
        local_video_path = storage.get_local_path(video_file_path)

        # 2. Perform processing using local paths
        # The logic for chunking, splitting, compressing remains here,
        # but it reads from local_video_path and writes to local_temp_dir.
        
        # Example for chunking:
        if chunk_duration := kwargs.get("chunk_duration"):
            logging.info(f"Chunking video '{local_video_path}' locally.")
            output_template = os.path.join(local_temp_dir, "chunk_%03d.mp4")
            stream = ffmpeg.input(local_video_path).output(
                output_template,
                map=0,
                f='segment',
                segment_time=chunk_duration,
                reset_timestamps=1,
                sc_threshold=0
            )
            _run_ffmpeg(stream, overwrite_output=True)
            
            # Get list of locally created chunks
            local_output_files = sorted([os.path.join(local_temp_dir, f) for f in os.listdir(local_temp_dir)])
        else:
            # If no operation, the "output" is just the original file
            local_output_files = [local_video_path]

        # 3. Upload results from the local temp dir to GCS
        gcs_output_files = []
        for local_file in local_output_files:
            gcs_path = os.path.join(output_directory, os.path.basename(local_file))
            storage.upload_file(local_file, gcs_path)
            gcs_output_files.append(ProcessedFile(output_path=gcs_path, source_operation="chunk")) # Example

    # 4. Clean up local temp files handled by StorageManager and TemporaryDirectory
    storage.cleanup_temp_files()

    end_time = time.time()
    time_taken = round(end_time - start_time, 2)

    result = VideoProcessingResult(
        input_video_path=video_file_path,
        operations_performed=["chunk"], # Example
        output_files=gcs_output_files,
        status="success",
        message="Successfully chunked video.",
        time_taken_seconds=time_taken
    )
    return result.dict()
