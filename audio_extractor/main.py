import click
import json
import os
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
        
        # Determine output directory for the JSON report
        effective_output_dir = output_dir if output_dir else os.path.dirname(video_file_path)
        
        # Create and save the JSON report
        base_filename = os.path.splitext(os.path.basename(video_file_path))[0]
        json_report_path = os.path.join(effective_output_dir, f"{base_filename}_audio_report.json")
        
        with open(json_report_path, 'w') as f:
            json.dump(result, f, indent=4)
            
        click.echo(f"Audio extraction complete. Report saved to: {json_report_path}")

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
