import click
import json
from .processor import process_video, VideoProcessingError

@click.command()
@click.argument('video_file_path', type=click.Path(exists=True, resolve_path=True))
@click.option('--output-dir', '-o', 'output_directory', type=click.Path(resolve_path=True), help="Directory to save the output files.")
@click.option('--split-timestamps', help='Comma-separated timestamps to split the video, e.g., "00:10-00:20,01:30-01:45".')
@click.option('--chunk-duration', type=int, help='Duration in seconds to chunk the video into.')
@click.option('--compress-resolution', help='Resolution to compress to, e.g., "1280x720" or "720p", "4K".')
@click.option('--compress-first', is_flag=True, help='Compress the video before splitting or chunking.')
def main(video_file_path, output_directory, split_timestamps, chunk_duration, compress_resolution, compress_first):
    """
    Processes a video by splitting, chunking, and/or compressing it.
    """
    try:
        result = process_video(
            video_file_path=video_file_path,
            output_directory=output_directory,
            split_timestamps=split_timestamps,
            chunk_duration=chunk_duration,
            compress_resolution=compress_resolution,
            compress_first=compress_first
        )
        click.echo(json.dumps(result, indent=4))
    except (FileNotFoundError, VideoProcessingError) as e:
        error_result = {
            "input_video_path": video_file_path,
            "status": "error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, indent=4), err=True)
        exit(1)

if __name__ == '__main__':
    main()
