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
    stream = ffmpeg.input(input_path).output(output_template, map=0, f='segment', segment_time=duration, c='copy')
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

def process_video(**kwargs) -> dict:
    start_time = time.time()
    
    video_file_path = kwargs.get("video_file_path")
    output_directory = kwargs.get("output_directory")
    split_timestamps = kwargs.get("split_timestamps")
    chunk_duration = kwargs.get("chunk_duration")
    compress_resolution = kwargs.get("compress_resolution")
    compress_first = kwargs.get("compress_first", False)

    if not os.path.exists(video_file_path):
        raise FileNotFoundError(f"Input file not found: {video_file_path}")

    if split_timestamps and chunk_duration:
        raise VideoProcessingError("Cannot use --split-timestamps and --chunk-duration at the same time.")

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)
    else:
        output_directory = os.path.dirname(video_file_path)

    operations_performed = []
    files_to_process = [video_file_path]
    processed_files_map = {}
    
    resolved_resolution = _resolve_resolution(compress_resolution)

    def run_compression(files, op_name="compress"):
        nonlocal operations_performed, processed_files_map
        operations_performed.append(op_name)
        compressed_files = _compress_videos(files, resolved_resolution, output_directory)
        for f in compressed_files:
            processed_files_map[f] = op_name
        return compressed_files

    def run_split(files, op_name="split"):
        nonlocal operations_performed, processed_files_map
        operations_performed.append(op_name)
        split_files = _split_video(files[0], split_timestamps, output_directory)
        for f in split_files:
            processed_files_map[f] = op_name
        return split_files

    def run_chunk(files, op_name="chunk"):
        nonlocal operations_performed, processed_files_map
        operations_performed.append(op_name)
        chunked_files = _chunk_video(files[0], chunk_duration, output_directory)
        for f in chunked_files:
            processed_files_map[f] = op_name
        return chunked_files

    if compress_first and resolved_resolution:
        files_to_process = run_compression(files_to_process)
    
    if split_timestamps:
        files_to_process = run_split(files_to_process)
    elif chunk_duration:
        files_to_process = run_chunk(files_to_process)
    
    if not compress_first and resolved_resolution:
        files_to_process = run_compression(files_to_process)

    output_files = [ProcessedFile(output_path=f, source_operation=processed_files_map.get(f, "original")) for f in files_to_process]
    
    end_time = time.time()
    time_taken = round(end_time - start_time, 2)

    result = VideoProcessingResult(
        input_video_path=video_file_path,
        operations_performed=operations_performed,
        output_files=output_files,
        status="success",
        message=f"Successfully performed: {', '.join(operations_performed) if operations_performed else 'No operations'}.",
        time_taken_seconds=time_taken
    )
    return result.dict()
