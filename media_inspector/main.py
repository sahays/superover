import click
import json
from .inspector import inspect_media, MediaInspectionError

@click.command()
@click.argument('file_path', type=click.Path(exists=True, resolve_path=True))
def main(file_path):
    """
    Inspects a media file and prints its metadata as JSON.
    """
    try:
        metadata = inspect_media(file_path)
        click.echo(json.dumps(metadata, indent=4))
    except MediaInspectionError as e:
        error_result = {
            "file_path": file_path,
            "status": "error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, indent=4), err=True)
        exit(1)

if __name__ == '__main__':
    main()