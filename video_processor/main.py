from fastapi import FastAPI, Request, HTTPException
import base64
import json
import os
from .processor import process_video
from common.storage import StorageManager

app = FastAPI()

@app.post("/")
async def handle_pubsub_message(request: Request):
    """
    Handles incoming Pub/Sub push messages for video processing.
    """
    body = await request.json()
    print(f"Received Pub/Sub message: {body}")

    if not body or "message" not in body or "data" not in body["message"]:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message payload")

    try:
        # The GCS event data is base64-encoded within the Pub/Sub message
        message_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
        event_data = json.loads(message_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error decoding message data: {e}")

    bucket = event_data.get("bucket")
    name = event_data.get("name")

    if not bucket or not name:
        raise HTTPException(status_code=400, detail="Invalid GCS event data in message")

    input_gcs_path = f"gs://{bucket}/{name}"
    output_dir_gcs_path = f"gs://{bucket}/processed/video_processor/{os.path.splitext(os.path.basename(name))[0]}/"

    print(f"Processing file: {input_gcs_path}")

    try:
        compress_first = os.getenv("COMPRESS_FIRST", "false").lower() in ("true", "1", "yes")
        
        result = process_video(
            video_file_path=input_gcs_path,
            output_directory=output_dir_gcs_path,
            chunk_duration=int(os.getenv("CHUNK_DURATION", 60)),
            compress_resolution=os.getenv("COMPRESS_RESOLUTION"),
            compress_first=compress_first
        )
        
        storage = StorageManager()
        report_path = os.path.join(output_dir_gcs_path, f"{os.path.splitext(os.path.basename(name))[0]}_report.json")
        storage.write_json(report_path, result)

        print(f"Successfully processed {input_gcs_path}. Report at: {report_path}")
        # Acknowledge the message with a 2xx status code
        return {"status": "success", "report_path": report_path}, 200

    except Exception as e:
        print(f"Error processing {input_gcs_path}: {e}")
        # Return a non-2xx status to let Pub/Sub retry the message
        raise HTTPException(status_code=500, detail=str(e))