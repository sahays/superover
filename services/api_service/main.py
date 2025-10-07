import os
import uuid
import json
import datetime
import logging
import traceback
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage, pubsub_v1, firestore
from google.auth import compute_engine
from google.auth.transport import requests as google_requests
import google.auth

# Load environment variables from project root .env file
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")
else:
    print(f"Warning: .env not found at {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
GCP_REGION = os.getenv("GCP_REGION", "asia-south1")
RAW_UPLOADS_BUCKET_NAME = os.getenv("RAW_UPLOADS_BUCKET_NAME")
JOBS_TOPIC_ID = os.getenv("JOBS_TOPIC_ID")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Log configuration on startup
logger.info("=" * 50)
logger.info("Super Over Alchemy API Service Starting")
logger.info("=" * 50)
logger.info(f"GCP_PROJECT_ID: {GCP_PROJECT_ID}")
logger.info(f"RAW_UPLOADS_BUCKET_NAME: {RAW_UPLOADS_BUCKET_NAME}")
logger.info(f"JOBS_TOPIC_ID: {JOBS_TOPIC_ID}")
logger.info(f"FRONTEND_URL: {FRONTEND_URL}")
logger.info("=" * 50)

# CORS Configuration
# Allow both production frontend and localhost for development
allowed_origins = [FRONTEND_URL]
if "localhost" not in FRONTEND_URL:
    # In production, also allow localhost for local development
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ])

logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Cloud Clients
credentials, project = google.auth.default()
storage_client = storage.Client(credentials=credentials, project=project)
publisher_client = pubsub_v1.PublisherClient()
firestore_client = firestore.Client(database="(default)")

# Get service account email for signing
SERVICE_ACCOUNT_EMAIL = None
try:
    # Try to get from environment first (for local dev with impersonation)
    SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")

    if not SERVICE_ACCOUNT_EMAIL:
        # Try to detect from credentials
        if hasattr(credentials, 'service_account_email'):
            SERVICE_ACCOUNT_EMAIL = credentials.service_account_email
        elif hasattr(credentials, 'signer_email'):
            SERVICE_ACCOUNT_EMAIL = credentials.signer_email
        else:
            # For user credentials in local dev, we'll use IAM signBlob API
            logger.info("Using IAM signBlob API for URL signing (user credentials detected)")
except Exception as e:
    logger.warning(f"Could not determine service account email: {e}")

# --- Helper Functions ---
def get_signing_credentials():
    """
    Get credentials suitable for signing URLs.
    Uses IAM signBlob API when using Compute Engine credentials.
    """
    from google.auth import impersonated_credentials
    from google.auth.compute_engine import IDTokenCredentials

    # Determine which service account to use
    signing_account = SERVICE_ACCOUNT_EMAIL
    if not signing_account:
        # When running on Cloud Run, get the service account from credentials
        try:
            if hasattr(credentials, 'service_account_email'):
                signing_account = credentials.service_account_email
                logger.info(f"Detected service account from credentials: {signing_account}")
            else:
                # Try to get from metadata server
                import requests
                response = requests.get(
                    'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email',
                    headers={'Metadata-Flavor': 'Google'},
                    timeout=2
                )
                signing_account = response.text
                logger.info(f"Detected service account from metadata: {signing_account}")
        except Exception as e:
            logger.warning(f"Could not get service account from metadata: {e}")
            # Fallback to the hardcoded service account name
            signing_account = f"super-over-services@{GCP_PROJECT_ID}.iam.gserviceaccount.com"

    logger.info(f"Creating signing credentials for: {signing_account}")

    # Create impersonated credentials that can sign
    signing_creds = impersonated_credentials.Credentials(
        source_credentials=credentials,
        target_principal=signing_account,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    return signing_creds

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
    logger.info(f"Received signed URL request for file: {request.file_name}")

    if not RAW_UPLOADS_BUCKET_NAME:
        logger.error("RAW_UPLOADS_BUCKET_NAME not configured")
        raise HTTPException(status_code=500, detail="Server is not configured for uploads.")

    try:
        logger.info(f"Creating bucket reference for: {RAW_UPLOADS_BUCKET_NAME}")
        bucket = storage_client.bucket(RAW_UPLOADS_BUCKET_NAME)
        blob = bucket.blob(request.file_name)

        logger.info(f"Generating signed URL with content_type: {request.content_type}")

        # Get credentials that can sign
        try:
            signing_creds = get_signing_credentials()
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=15),
                method="PUT",
                content_type=request.content_type,
                credentials=signing_creds,
            )
        except Exception as sign_error:
            logger.warning(f"Failed to use impersonated credentials: {sign_error}")
            # Fallback: try with default credentials (works if they have a private key)
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=15),
                method="PUT",
                content_type=request.content_type,
            )

        gcs_path = f"gs://{RAW_UPLOADS_BUCKET_NAME}/{request.file_name}"
        logger.info(f"Successfully generated signed URL for: {gcs_path}")
        return {"signed_url": url, "gcs_path": gcs_path}
    except Exception as e:
        logger.error(f"Failed to generate signed URL: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate signed URL: {str(e)}")

@app.post("/v1/scene-analysis/jobs")
async def create_scene_analysis_job(request: JobRequest):
    """
    Creates a new scene analysis job by publishing a message to Pub/Sub.
    """
    logger.info(f"Received job creation request for: {request.gcs_path}")

    if not GCP_PROJECT_ID or not JOBS_TOPIC_ID:
        logger.error(f"Missing config - GCP_PROJECT_ID: {GCP_PROJECT_ID}, JOBS_TOPIC_ID: {JOBS_TOPIC_ID}")
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
        logger.info(f"Creating Firestore document for job: {job_id}")
        job_ref = firestore_client.collection("sceneAnalysisJobs").document(job_id)
        job_ref.set(job_data)

        # 2. Publish job message to Pub/Sub as JSON
        logger.info(f"Publishing job to Pub/Sub topic: {topic_path}")
        message_json = json.dumps(job_data)
        future = publisher_client.publish(topic_path, data=message_json.encode("utf-8"))
        future.result()  # Wait for publish to complete

        logger.info(f"Successfully created job: {job_id}")
        return {"job_id": job_id, "status": "queued"}
    except Exception as e:
        logger.error(f"Failed to create job: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

@app.get("/v1/scene-analysis/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Gets the status of a scene analysis job from Firestore.
    """
    logger.info(f"Fetching job status for: {job_id}")

    try:
        job_ref = firestore_client.collection("sceneAnalysisJobs").document(job_id)
        doc = job_ref.get()
        if not doc.exists:
            logger.warning(f"Job not found: {job_id}")
            raise HTTPException(status_code=404, detail="Job not found")

        job_data = doc.to_dict()
        logger.info(f"Found job {job_id} with status: {job_data.get('status')}")
        return job_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve job status: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve job status: {str(e)}")
