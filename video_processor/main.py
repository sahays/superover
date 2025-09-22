from fastapi import FastAPI, Request, HTTPException
import base64
import json
import os
from .processor import process_video, VideoProcessingError
from common.storage import StorageManager

app = FastAPI()

@app.post("/")
async def handle_gcs_event(request: Request):
    """
    Handles incoming CloudEvents from GCS via Eventarc.
    """
    body = await request.json()
    print(f"Received CloudEvent: {body}")

    # Extract the GCS event data from the CloudEvent payload
    if not body or "message" not in body or "data" not in body["message"]:
        raise HTTPException(status_code=400, detail="Invalid CloudEvent payload: missing message data")

    try:
        message_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
        event_data = json.loads(message_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error decoding message data: {e}")

    bucket = event_data.get("bucket")
    name = event_data.get("name")

    if not bucket or not name:
        raise HTTPException(status_code=400, detail="Invalid GCS event data: missing bucket or name")

    # Define input and output paths
    input_gcs_path = f"gs://{bucket}/{name}"
    
    # Define a structured output path. Example: gs://my-bucket/processed/video_processor/original_filename/
    output_dir_gcs_path = f"gs://{bucket}/processed/video_processor/{os.path.splitext(os.path.basename(name))[0]}/"

    print(f"Processing file: {input_gcs_path}")

    try:
        # The core processing logic is called here.
        # Parameters like chunk_duration can be passed via environment variables.
        result = process_video(
            video_file_path=input_gcs_path,
            output_directory=output_dir_gcs_path,
            chunk_duration=int(os.getenv("CHUNK_DURATION", 60)), # Example: configure via env var
            compress_resolution=os.getenv("COMPRESS_RESOLUTION") # Example
        )
        
        # Save the final report to the output directory in GCS
        storage = StorageManager()
        report_path = os.path.join(output_dir_gcs_path, "processing_report.json")
        storage.write_json(report_path, result)

        print(f"Successfully processed {input_gcs_path}. Report at: {report_path}")
        return {"status": "success", "report_path": report_path}, 200

    except Exception as e:
        print(f"Error processing {input_gcs_path}: {e}")
        # A non-2xx status code will cause Eventarc to attempt a retry.
        raise HTTPException(status_code=500, detail=str(e))