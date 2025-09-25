import os
import ffmpeg
import re
import time
import logging
import tempfile
from .models import VideoProcessingResult, ProcessedFile
from common.storage import StorageManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoProcessingError(Exception):
    pass

RESOLUTION_SHORTHANDS = {
    "360p": "640x360", "480p": "854x480", "720p": "1280x720",
    "1080p": "1920x1080", "1440p": "2560x1440", "2k": "2560x1440",
    "2160p": "3840x2160", "4k": "3840x2160",
}

def _resolve_resolution(res_string: str) -> str:
    if not res_string: return None
    res_string = res_string.lower()
    if res_string in RESOLUTION_SHORTHANDS: return RESOLUTION_SHORTHANDS[res_string]
    if re.match(r'^\d+x\d+$', res_string): return res_string
    raise VideoProcessingError(f"Invalid resolution format: '{res_string}'.")

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
        output_template, map=0, f='segment', segment_time=duration,
        reset_timestamps=1, sc_threshold=0
    )
    _run_ffmpeg(stream, overwrite_output=True)
    output_files = [os.path.join(output_dir, f) for f in sorted(os.listdir(output_dir)) if f.startswith('chunk_')]
    logging.info(f"Finished chunking. Created {len(output_files)} files.")
    return output_files

def _compress_videos(input_paths, resolution, output_dir):
    logging.info(f"Compressing {len(input_paths)} video file(s) to {resolution}.")
    output_files = []
    width, height = map(int, resolution.split('x'))
    for i, path in enumerate(input_paths):
        base_name = os.path.splitext(os.path.basename(path))[0]
        output_path = os.path.join(output_dir, f"compressed_{i}_{base_name}.mp4")
        input_stream = ffmpeg.input(path)
        video_stream = input_stream.video.filter('scale', width, height)
        stream = ffmpeg.output(video_stream, input_stream.audio, output_path, vcodec='libx264', pix_fmt='yuv420p')
        _run_ffmpeg(stream, overwrite_output=True)
        output_files.append(output_path)
    logging.info("Finished compression.")
    return output_files

def process_video(**kwargs) -> dict:
    start_time = time.time()
    storage = StorageManager()
    
    video_file_path = kwargs.get("video_file_path")
    output_directory = kwargs.get("output_directory")
    split_timestamps = kwargs.get("split_timestamps")
    chunk_duration = kwargs.get("chunk_duration")
    compress_resolution = kwargs.get("compress_resolution")
    
    operations_performed = []
    processed_files_map = {}

    with tempfile.TemporaryDirectory() as local_temp_dir:
        local_video_path = storage.get_local_path(video_file_path)
        files_to_process_locally = [local_video_path]

        if compress_resolution:
            resolved_resolution = _resolve_resolution(compress_resolution)
            operations_performed.append("compress")
            files_to_process_locally = _compress_videos(files_to_process_locally, resolved_resolution, local_temp_dir)
            for f in files_to_process_locally: processed_files_map[f] = "compress"

        if split_timestamps:
            operations_performed.append("split")
            # Splitting needs the original single file, not a list
            source_for_split = files_to_process_locally[0]
            files_to_process_locally = _split_video(source_for_split, split_timestamps, local_temp_dir)
            for f in files_to_process_locally: processed_files_map[f] = "split"
        
        elif chunk_duration:
            operations_performed.append("chunk")
            source_for_chunk = files_to_process_locally[0]
            files_to_process_locally = _chunk_video(source_for_chunk, chunk_duration, local_temp_dir)
            for f in files_to_process_locally: processed_files_map[f] = "chunk"

        final_output_files = []
        for local_file in files_to_process_locally:
            destination_path = os.path.join(output_directory, os.path.basename(local_file))
            storage.move_file(local_file, destination_path)
            final_output_files.append(ProcessedFile(
                output_path=destination_path,
                source_operation=processed_files_map.get(local_file, "original")
            ))

    storage.cleanup_temp_files()
    time_taken = round(time.time() - start_time, 2)

    return VideoProcessingResult(
        input_video_path=video_file_path,
        operations_performed=operations_performed,
        output_files=final_output_files,
        status="success",
        message=f"Successfully performed: {', '.join(operations_performed) if operations_performed else 'No operations'}.",
        time_taken_seconds=time_taken
    ).dict()