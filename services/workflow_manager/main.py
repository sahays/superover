from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import re
from google.cloud import firestore

app = FastAPI(title="Workflow Manager Service", version="1.0.0")

# --- Configuration: The list of available services that can be used in a pipeline ---
# This acts as a security and validation layer.
AVAILABLE_OPERATIONS = {
    "video-processor": {"topic": "video-processor-jobs"},
    "audio-extractor": {"topic": "audio-extractor-jobs"},
    "scene-analyzer": {"topic": "scene-analyzer-jobs"},
    "media-inspector": {"topic": "media-inspector-jobs"}
}

db = firestore.Client()

# Pydantic models
class PipelineStep(BaseModel):
    serviceName: str

class CreatePipelineRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    steps: List[PipelineStep]

class UpdatePipelineRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[PipelineStep]] = None

def _slugify(text: str) -> str:
    """Converts a string to a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    return text

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Workflow Manager Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "GET / - Service info",
            "GET /health - Health check",
            "GET /operations - List available operations",
            "GET /pipelines - List all pipelines",
            "POST /pipelines - Create new pipeline",
            "GET /pipelines/{pipeline_id} - Get specific pipeline",
            "PUT /pipelines/{pipeline_id} - Update pipeline",
            "DELETE /pipelines/{pipeline_id} - Delete pipeline"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "workflow-manager",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }

@app.get("/operations")
async def list_available_operations():
    """Returns the dictionary of available operations."""
    return {"operations": AVAILABLE_OPERATIONS}

@app.post("/pipelines")
async def create_pipeline(pipeline: CreatePipelineRequest):
    """Creates a new pipeline document in Firestore."""
    pipeline_id = _slugify(pipeline.name)
    if db.collection('pipelines').document(pipeline_id).get().exists:
        raise HTTPException(status_code=409, detail=f"Pipeline with ID '{pipeline_id}' already exists.")

    validated_steps = []
    for i, step in enumerate(pipeline.steps):
        if step.serviceName not in AVAILABLE_OPERATIONS:
            raise HTTPException(status_code=400, detail=f"Invalid step: '{step.serviceName}' is not a recognized operation.")

        validated_steps.append({
            "order": i + 1,
            "serviceName": step.serviceName,
            "topic": AVAILABLE_OPERATIONS[step.serviceName]["topic"]
        })

    pipeline_data = {
        "pipelineId": pipeline_id,
        "name": pipeline.name,
        "description": pipeline.description,
        "steps": validated_steps
    }

    db.collection('pipelines').document(pipeline_id).set(pipeline_data)
    return pipeline_data

@app.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Retrieves a single pipeline document."""
    doc = db.collection('pipelines').document(pipeline_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    return doc.to_dict()

@app.get("/pipelines")
async def list_pipelines():
    """Lists all pipeline documents."""
    pipelines = []
    for doc in db.collection('pipelines').stream():
        pipelines.append(doc.to_dict())
    return {"pipelines": pipelines}

@app.put("/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: str, pipeline: UpdatePipelineRequest):
    """Updates an existing pipeline document."""
    doc_ref = db.collection('pipelines').document(pipeline_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    current_data = doc.to_dict()
    update_data = {}

    if pipeline.name is not None:
        update_data["name"] = pipeline.name
    if pipeline.description is not None:
        update_data["description"] = pipeline.description
    if pipeline.steps is not None:
        validated_steps = []
        for i, step in enumerate(pipeline.steps):
            if step.serviceName not in AVAILABLE_OPERATIONS:
                raise HTTPException(status_code=400, detail=f"Invalid step: '{step.serviceName}' is not a recognized operation.")

            validated_steps.append({
                "order": i + 1,
                "serviceName": step.serviceName,
                "topic": AVAILABLE_OPERATIONS[step.serviceName]["topic"]
            })
        update_data["steps"] = validated_steps

    doc_ref.update(update_data)

    # Return updated document
    updated_doc = doc_ref.get()
    return updated_doc.to_dict()

@app.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Deletes a pipeline document."""
    doc_ref = db.collection('pipelines').document(pipeline_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    doc_ref.delete()
    return {"message": "Pipeline deleted successfully"}