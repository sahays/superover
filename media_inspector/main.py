import click
import json
import os
from .inspector import inspect_media, MediaInspectionError

@click.command()
@click.argument('file_path', type=click.Path(exists=True, resolve_path=True))
@click.option('--output-dir', '-o', 'output_dir', type=click.Path(resolve_path=True), help="Directory to save the inspection report.")
def main(file_path, output_dir):
    """
    Inspects a media file and prints its metadata as JSON.
    """
    try:
        metadata = inspect_media(file_path)
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(output_dir, f"{base_filename}_metadata.json")
            
            with open(output_path, 'w') as f:
                json.dump(metadata, f, indent=4)
            
            click.echo(f"Inspection report saved to: {output_path}")
        else:
            click.echo(json.dumps(metadata, indent=4))

    except MediaInspectionError as e:
        error_result = {
            "file_path": file_path,
            "status": "error",
            "message": str(e)
        }
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(output_dir, f"{base_filename}_error.json")
            
            with open(output_path, 'w') as f:
                json.dump(error_result, f, indent=4)
            
            click.echo(f"Error report saved to: {output_path}", err=True)
        else:
            click.echo(json.dumps(error_result, indent=4), err=True)
        
        exit(1)

if __name__ == '__main__':
    main()
