from fastapi import FastAPI, Request, HTTPException
import base64
import json
import os
from .inspector import inspect_media, MediaInspectionError
from common.storage import StorageManager

app = FastAPI()

@app.post("/")
async def handle_gcs_event(request: Request):
    """
    Handles incoming CloudEvents from GCS for media inspection.
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
    output_dir_gcs_path = f"gs://{bucket}/processed/media_inspector/"

    print(f"Starting media inspection for: {input_gcs_path}")

    try:
        metadata = inspect_media(file_path=input_gcs_path)
        
        storage = StorageManager()
        base_filename = os.path.splitext(os.path.basename(name))[0]
        report_path = os.path.join(output_dir_gcs_path, f"{base_filename}_metadata.json")
        storage.write_json(report_path, metadata)

        print(f"Successfully inspected {input_gcs_path}. Report at: {report_path}")
        return {"status": "success", "report_path": report_path}, 200

    except Exception as e:
        print(f"Error inspecting {input_gcs_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))