import os
import json
import logging
import tempfile
import datetime
import sys
from pathlib import Path
from google.cloud import firestore, storage

# Import the shared library functions
from media_utils import inspector, processor, audio

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables & Global Clients ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
PROCESSED_OUTPUTS_BUCKET_NAME = os.getenv("PROCESSED_OUTPUTS_BUCKET_NAME")

if not all([GCP_PROJECT_ID, PROCESSED_OUTPUTS_BUCKET_NAME]):
    raise ValueError("Missing one or more critical environment variables: GCP_PROJECT_ID, PROCESSED_OUTPUTS_BUCKET_NAME")

firestore_client = firestore.Client()
storage_client = storage.Client()

# --- Core Processing Logic ---
def process_pipeline(job_data: dict):
    """
    Executes the entire synchronous scene analysis pipeline for a given job.
    """
    job_id = job_data["job_id"]
    gcs_path = job_data["gcs_path"]
    logging.info(f"[{job_id}] Starting pipeline for {gcs_path}")

    job_ref = firestore_client.collection("sceneAnalysisJobs").document(job_id)
    job_ref.update({"status": "processing", "worker_start_time": datetime.datetime.utcnow().isoformat()})

    with tempfile.TemporaryDirectory() as temp_dir:
        local_video_path = os.path.join(temp_dir, "original_video")
        
        try:
            # 1. Download video from GCS
            logging.info(f"[{job_id}] Downloading video...")
            bucket_name, blob_name = gcs_path[5:].split("/", 1)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.download_to_filename(local_video_path)

            # 2. Inspect Media
            logging.info(f"[{job_id}] Inspecting media...")
            media_info = inspector.inspect_media(local_video_path)
            job_ref.update({"media_info": media_info.dict()})

            # 3. Run the rest of the pipeline (compress, chunk, etc.)
            # This is a placeholder for the full pipeline logic from the LLD.
            # For now, we'll just simulate a successful completion.
            logging.info(f"[{job_id}] Running media processing (compress, chunk, analyze)...")
            # In a real implementation, you would call:
            # compressed_path = processor.compress_video(...)
            # chunks = processor.chunk_video(...)
            # audio_path = audio.extract_audio(...)
            # analysis = gemini_analyzer.analyze(...)
            
            # 4. Upload results (placeholder)
            final_analysis_path = os.path.join(temp_dir, "analysis.json")
            with open(final_analysis_path, "w") as f:
                json.dump({"result": "success"}, f)
            
            processed_bucket = storage_client.bucket(PROCESSED_OUTPUTS_BUCKET_NAME)
            result_blob = processed_bucket.blob(f"{job_id}/analysis.json")
            result_blob.upload_from_filename(final_analysis_path)

            # 5. Update Firestore with final status
            logging.info(f"[{job_id}] Pipeline completed successfully.")
            job_ref.update({
                "status": "completed",
                "worker_end_time": datetime.datetime.utcnow().isoformat(),
                "results_path": f"gs://{PROCESSED_OUTPUTS_BUCKET_NAME}/{job_id}/"
            })

        except Exception as e:
            logging.error(f"[{job_id}] Pipeline failed: {str(e)}")
            job_ref.update({
                "status": "failed",
                "error": str(e),
                "worker_end_time": datetime.datetime.utcnow().isoformat()
            })

# --- Main Execution for Cloud Run Job ---
def main():
    """
    Cloud Run Job execution: Reads job data from Pub/Sub push request,
    processes a single job, then exits.
    """
    import base64

    # When Pub/Sub pushes to Cloud Run Jobs, the message comes in CLOUD_EVENTS_DATA
    # But we need to handle it as a standard input from the push endpoint
    # The message data is base64 encoded in the Pub/Sub message

    # Try to get from environment first (Cloud Run Jobs with Pub/Sub integration)
    cloud_events_data = os.getenv("CLOUD_EVENTS_DATA")

    if cloud_events_data:
        try:
            # Parse the Cloud Events format
            event_data = json.loads(cloud_events_data)

            # The actual message is base64 encoded in event_data.message.data
            if "message" in event_data and "data" in event_data["message"]:
                message_data = base64.b64decode(event_data["message"]["data"]).decode("utf-8")
                job_data = json.loads(message_data)
            else:
                # Direct JSON
                job_data = event_data

            logging.info(f"Processing job: {job_data.get('job_id', 'unknown')}")

            # Process the pipeline
            process_pipeline(job_data)

            logging.info("Job completed successfully")
            sys.exit(0)

        except Exception as e:
            logging.error(f"Job failed with error: {e}", exc_info=True)
            sys.exit(1)
    else:
        logging.error("No CLOUD_EVENTS_DATA environment variable found")
        logging.info("Environment variables: " + str(dict(os.environ)))
        sys.exit(1)

if __name__ == "__main__":
    main()
