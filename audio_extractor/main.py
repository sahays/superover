from fastapi import FastAPI, Request, HTTPException
import base64
import json
import os
from .extractor import extract_audio, AudioExtractionError
from common.storage import StorageManager

app = FastAPI()

@app.post("/")
async def handle_gcs_event(request: Request):
    """
    Handles incoming CloudEvents from GCS for audio extraction.
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
    name = event_data.get("name")

    if not bucket or not name:
        raise HTTPException(status_code=400, detail="Invalid GCS event data: missing bucket or name")

    input_gcs_path = f"gs://{bucket}/{name}"
    output_dir_gcs_path = f"gs://{bucket}/processed/audio_extractor/{os.path.splitext(os.path.basename(name))[0]}/"

    print(f"Starting audio extraction for: {input_gcs_path}")

    try:
        result = extract_audio(
            video_file_path=input_gcs_path,
            output_directory=output_dir_gcs_path
        )
        
        storage = StorageManager()
        report_path = os.path.join(output_dir_gcs_path, "extraction_report.json")
        storage.write_json(report_path, result)

        print(f"Successfully extracted audio from {input_gcs_path}. Report at: {report_path}")
        return {"status": "success", "report_path": report_path}, 200

    except Exception as e:
        print(f"Error extracting audio from {input_gcs_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))