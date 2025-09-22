import functions_framework
import os
import uuid
import datetime
from google.cloud import firestore
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1.types import Execution


@functions_framework.http
def create_job(request):
    """
    HTTP Cloud Function to create a new job in Firestore and trigger a Cloud Workflow.
    Expects a JSON payload with 'sourceFile' and 'pipelineId'.

    Example Payload:
    {
        "sourceFile": "gs://your-bucket/videos/your-video.mp4",
        "pipelineId": "full-analysis-pipeline"
    }
    """
    # --- 1. Configuration and Validation ---
    request_json = request.get_json(silent=True)
    if (
        not request_json
        or "sourceFile" not in request_json
        or "pipelineId" not in request_json
    ):
        return (
            'Invalid request: JSON payload must contain "sourceFile" and "pipelineId".',
            400,
        )

    source_file = request_json["sourceFile"]
    pipeline_id = request_json["pipelineId"]

    # Get configuration from environment variables
    project_id = os.environ.get("GCP_PROJECT")
    location = os.environ.get("GCP_LOCATION", "asia-south1")
    workflow_name = os.environ.get("WORKFLOW_NAME", "pipeline-orchestrator")

    if not project_id:
        return "Configuration error: GCP_PROJECT environment variable not set.", 500

    # --- 2. Create Job in Firestore ---
    db = firestore.Client()
    job_id = str(uuid.uuid4())

    job_doc_ref = db.collection("jobs").document(job_id)

    job_data = {
        "jobId": job_id,
        "status": "PENDING",
        "pipelineId": pipeline_id,
        "sourceFile": source_file,
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
        return f"Internal server error: Could not create job in Firestore.", 500

    # --- 3. Trigger Cloud Workflow ---
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
        return f"Internal server error: Could not start workflow.", 500

    # --- 4. Return Job ID to Caller ---
    return {"jobId": job_id}, 200
