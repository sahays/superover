from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import datetime
from google.cloud import firestore
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1.types import Execution

app = FastAPI(title="Job Creator Service", version="1.0.0")

# Pydantic models
class CreateJobRequest(BaseModel):
    sourceFile: str
    pipelineId: str

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Job Creator Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "GET / - Service info",
            "GET /health - Health check",
            "POST /jobs - Create new job",
            "GET /jobs/{job_id} - Get job status"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "job-creator",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "config": {
            "project_id": os.environ.get("GCP_PROJECT"),
            "location": os.environ.get("GCP_LOCATION", "asia-south1"),
            "workflow_name": os.environ.get("WORKFLOW_NAME", "pipeline-orchestrator")
        }
    }

@app.post("/jobs")
async def create_job(job_request: CreateJobRequest):
    """
    Creates a new job in Firestore and triggers a Cloud Workflow.
    """
    # Get configuration from environment variables
    project_id = os.environ.get("GCP_PROJECT")
    location = os.environ.get("GCP_LOCATION", "asia-south1")
    workflow_name = os.environ.get("WORKFLOW_NAME", "pipeline-orchestrator")

    if not project_id:
        raise HTTPException(status_code=500, detail="Configuration error: GCP_PROJECT environment variable not set.")

    # Create Job in Firestore
    db = firestore.Client()
    job_id = str(uuid.uuid4())

    job_doc_ref = db.collection("jobs").document(job_id)

    job_data = {
        "jobId": job_id,
        "status": "PENDING",
        "pipelineId": job_request.pipelineId,
        "sourceFile": job_request.sourceFile,
        "createdAt": datetime.datetime.utcnow(),
        "updatedAt": datetime.datetime.utcnow(),
        "retryCount": 0,
        "checkpoints": {},
        "progress": {},
        "outputs": {},
        "error": None,
    }

    try:
        job_doc_ref.set(job_data)
        print(f"Successfully created job '{job_id}' in Firestore.")
    except Exception as e:
        print(f"Error creating job in Firestore: {e}")
        raise HTTPException(status_code=500, detail="Internal server error: Could not create job in Firestore.")

    # Trigger Cloud Workflow
    execution_client = executions_v1.ExecutionsClient()

    parent = f"projects/{project_id}/locations/{location}/workflows/{workflow_name}"
    execution = Execution(argument=f'{{"jobId": "{job_id}"}}')

    try:
        response = execution_client.create_execution(parent=parent, execution=execution)
        print(f"Successfully started workflow execution: {response.name}")
    except Exception as e:
        # If workflow fails, update Firestore to reflect the failure
        job_doc_ref.update(
            {"status": "FAILED", "error": f"Failed to start workflow: {e}"}
        )
        print(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error: Could not start workflow.")

    return {"jobId": job_id}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a specific job."""
    db = firestore.Client()
    job_doc = db.collection("jobs").document(job_id).get()

    if not job_doc.exists:
        raise HTTPException(status_code=404, detail="Job not found.")

    return job_doc.to_dict()