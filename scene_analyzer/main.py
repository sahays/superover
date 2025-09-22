from fastapi import FastAPI, Request, HTTPException
import base64
import json
import os
from .analyzer import analyze_scenes, SceneAnalysisError
from common.storage import StorageManager

app = FastAPI()

@app.post("/")
async def handle_gcs_event(request: Request):
    """
    Handles incoming CloudEvents from GCS for scene analysis.
    The trigger for this service should be a manifest file from a video processor.
    """
    body = await request.json()
    print(f"Received CloudEvent: {body}")

    if not body or "message" not in body or "data" not in body["message"]:
        raise HTTPException(status_code=400, detail="Invalid CloudEvent payload: missing message data")

    try:
        message_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
        event_data = json.loads(message_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error decoding message data: {e}")

    bucket = event_data.get("bucket")
    name = event_data.get("name") # This should be the path to the manifest.json

    if not bucket or not name:
        raise HTTPException(status_code=400, detail="Invalid GCS event data: missing bucket or name")

    # Ensure we are only processing manifest files
    if not name.endswith('_report.json'):
        print(f"Skipping file {name} as it is not a report manifest.")
        return {"status": "skipped", "reason": "Not a report manifest file"}, 200

    input_manifest_gcs_path = f"gs://{bucket}/{name}"
    
    # Define a structured output path.
    # e.g., gs://my-bucket/processed/scene_analyzer/original_video_name/
    original_video_name = name.split('/')[-2] # Assumes path like .../video_processor/original_name/report.json
    output_dir_gcs_path = f"gs://{bucket}/processed/scene_analyzer/{original_video_name}/"

    print(f"Starting scene analysis for manifest: {input_manifest_gcs_path}")

    try:
        report_paths, time_taken = analyze_scenes(
            manifest_file_path=input_manifest_gcs_path,
            output_directory=output_dir_gcs_path
        )
        
        # Create the final manifest report
        storage = StorageManager()
        final_manifest_path = os.path.join(output_dir_gcs_path, "analysis_manifest.json")
        
        result = {
            "source_manifest_path": input_manifest_gcs_path,
            "analysis_reports": report_paths,
            "status": "success",
            "message": f"Successfully analyzed {len(report_paths)} scenes.",
            "time_taken_seconds": round(time_taken, 2)
        }
        storage.write_json(final_manifest_path, result)

        print(f"Successfully analyzed scenes. Final manifest at: {final_manifest_path}")
        return {"status": "success", "manifest_path": final_manifest_path}, 200

    except Exception as e:
        print(f"Error analyzing scenes for manifest {input_manifest_gcs_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))