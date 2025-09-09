import click
import json
from .extractor import extract_audio, AudioExtractionError

@click.command()
@click.argument('video_file_path', type=click.Path(exists=True, resolve_path=True))
@click.option('--output-dir', '-o', 'output_dir', type=click.Path(resolve_path=True), help="Directory to save the extracted audio files.")
def main(video_file_path, output_dir):
    """
    Extracts all audio tracks from a video file into individual files and one combined file.
    """
    try:
        result = extract_audio(video_file_path, output_dir)
        click.echo(json.dumps(result, indent=4))
    except AudioExtractionError as e:
        error_result = {
            "input_video_path": video_file_path,
            "status": "error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, indent=4), err=True)
        exit(1)

if __name__ == '__main__':
    main()