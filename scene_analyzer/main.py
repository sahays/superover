import click
import json
import os
from .analyzer import analyze_scenes, SceneAnalysisError

@click.command()
@click.argument('manifest_file_path', type=click.Path(exists=True, resolve_path=True))
@click.option('--output-dir', '-o', 'output_directory', type=click.Path(resolve_path=True), help="Directory to save the analysis report.")
def main(manifest_file_path, output_directory):
    """
    Analyzes video scenes from a manifest file using the Gemini API.
    """
    try:
        click.echo(f"Starting scene analysis for: {manifest_file_path}")
            
        result = analyze_scenes(manifest_file_path)
        
        # Determine output directory
        if not output_directory:
            output_directory = os.path.dirname(manifest_file_path)
        else:
            os.makedirs(output_directory, exist_ok=True)

        base_filename = os.path.splitext(os.path.basename(manifest_file_path))[0]

        # Save the analysis report
        report_path = os.path.join(output_directory, f"{base_filename}_analyzed.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        click.echo(f"Analysis complete. Report saved to: {report_path}")

    except (FileNotFoundError, SceneAnalysisError) as e:
        error_result = {
            "source_manifest_path": manifest_file_path,
            "status": "error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, indent=4), err=True)
        exit(1)

if __name__ == '__main__':
    main()
