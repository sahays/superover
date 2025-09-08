import typer
import json
from .inspector import inspect_media, MediaInspectionError

app = typer.Typer()

@app.callback(invoke_without_command=True)
def main(file_path: str = typer.Argument(..., help="The absolute path to the media file.")):
    """
    Inspects a media file and prints its metadata as JSON.
    """
    try:
        metadata = inspect_media(file_path)
        print(json.dumps(metadata, indent=4))
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except MediaInspectionError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
