import os
import uuid
import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage, pubsub_v1, firestore

# --- Pydantic Models for API Requests ---
class SignedUrlRequest(BaseModel):
    file_name: str
    content_type: str

class JobRequest(BaseModel):
    gcs_path: str

# --- FastAPI Application Setup ---
app = FastAPI(title="Super Over Alchemy API Service")

# Environment Variables
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
RAW_UPLOADS_BUCKET_NAME = os.getenv("RAW_UPLOADS_BUCKET_NAME")
JOBS_TOPIC_ID = os.getenv("JOBS_TOPIC_ID")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Cloud Clients
storage_client = storage.Client()
publisher_client = pubsub_v1.PublisherClient()
firestore_client = firestore.Client(database="(default)")

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "API service is running"}

@app.get("/health")
def health_check():
    """
    Health check endpoint to verify service status.
    """
    # Simple check to ensure essential config is present
    if not GCP_PROJECT_ID or not RAW_UPLOADS_BUCKET_NAME:
        raise HTTPException(status_code=503, detail="Service Unavailable: Missing critical configuration.")
    
    return {"status": "ok", "project_id": GCP_PROJECT_ID}

@app.post("/v1/uploads/signed-url")
async def create_signed_url(request: SignedUrlRequest):
    """
    Generates a GCS signed URL for direct browser uploads.
    """
    if not RAW_UPLOADS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Server is not configured for uploads.")

    bucket = storage_client.bucket(RAW_UPLOADS_BUCKET_NAME)
    blob = bucket.blob(request.file_name)

    try:
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=request.content_type,
        )
        return {"signed_url": url, "gcs_path": f"gs://{RAW_UPLOADS_BUCKET_NAME}/{request.file_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate signed URL: {str(e)}")

@app.post("/v1/scene-analysis/jobs")
async def create_scene_analysis_job(request: JobRequest):
    """
    Creates a new scene analysis job by publishing a message to Pub/Sub.
    """
    if not GCP_PROJECT_ID or not JOBS_TOPIC_ID:
        raise HTTPException(status_code=500, detail="Server is not configured for job creation.")

    job_id = str(uuid.uuid4())
    topic_path = publisher_client.topic_path(GCP_PROJECT_ID, JOBS_TOPIC_ID)
    
    job_data = {
        "job_id": job_id,
        "gcs_path": request.gcs_path,
        "status": "queued",
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    try:
        # 1. Create initial job status in Firestore
        job_ref = firestore_client.collection("sceneAnalysisJobs").document(job_id)
        job_ref.set(job_data)

        # 2. Publish job message to Pub/Sub as JSON
        message_json = json.dumps(job_data)
        future = publisher_client.publish(topic_path, data=message_json.encode("utf-8"))
        future.result()  # Wait for publish to complete

        return {"job_id": job_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

@app.get("/v1/scene-analysis/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Gets the status of a scene analysis job from Firestore.
    """
    try:
        job_ref = firestore_client.collection("sceneAnalysisJobs").document(job_id)
        doc = job_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Job not found")
        return doc.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve job status: {str(e)}")
