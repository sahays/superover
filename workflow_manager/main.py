import functions_framework
import re
from google.cloud import firestore

# --- Configuration: The list of available services that can be used in a pipeline ---
# This acts as a security and validation layer.
AVAILABLE_OPERATIONS = {
    "video-processor": {"topic": "video-processor-jobs"},
    "audio-extractor": {"topic": "audio-extractor-jobs"},
    "scene-analyzer": {"topic": "scene-analyzer-jobs"},
    "media-inspector": {"topic": "media-inspector-jobs"}
}

db = firestore.Client()

def _slugify(text):
    """Converts a string to a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    return text

@functions_framework.http
def manage_workflow(request):
    """
    A CRUD HTTP Cloud Function to manage workflow pipelines in Firestore.
    - POST /: Creates a new pipeline.
    - GET /: Lists all pipelines.
    - GET /operations: Lists all available operations for pipelines.
    - GET /<pipeline_id>: Retrieves a specific pipeline.
    - PUT /<pipeline_id>: Updates a pipeline.
    - DELETE /<pipeline_id>: Deletes a pipeline.
    """
    path = request.path.strip('/')
    path_parts = path.split('/')
    
    if request.method == 'GET' and path == 'operations':
        return list_available_operations()

    pipeline_id = path_parts[0] if path_parts and path_parts[0] != 'operations' else None

    if request.method == 'POST' and not pipeline_id:
        return create_pipeline(request)
    elif request.method == 'GET' and not pipeline_id:
        return list_pipelines(request)
    elif request.method == 'GET' and pipeline_id:
        return get_pipeline(pipeline_id)
    elif request.method == 'PUT' and pipeline_id:
        return update_pipeline(request, pipeline_id)
    elif request.method == 'DELETE' and pipeline_id:
        return delete_pipeline(pipeline_id)
    else:
        return 'Method or path not supported.', 405

def list_available_operations():
    """Returns the dictionary of available operations."""
    return {"operations": AVAILABLE_OPERATIONS}, 200

def create_pipeline(request):
    """Creates a new pipeline document in Firestore."""
    data = request.get_json(silent=True)
    if not data or 'name' not in data or 'steps' not in data:
        return 'Invalid request: JSON payload must contain "name" and "steps".', 400

    pipeline_id = _slugify(data['name'])
    if db.collection('pipelines').document(pipeline_id).get().exists:
        return f"Error: Pipeline with ID '{pipeline_id}' already exists.", 409

    validated_steps = []
    for i, step in enumerate(data.get('steps', [])):
        service_name = step.get('serviceName')
        if service_name not in AVAILABLE_OPERATIONS:
            return f"Invalid step: '{service_name}' is not a recognized operation.", 400
        
        validated_steps.append({
            "order": i + 1,
            "serviceName": service_name,
            "topic": AVAILABLE_OPERATIONS[service_name]["topic"]
        })

    pipeline_data = {
        "pipelineId": pipeline_id,
        "name": data['name'],
        "description": data.get('description', ''),
        "steps": validated_steps
    }

    db.collection('pipelines').document(pipeline_id).set(pipeline_data)
    return pipeline_data, 201

def get_pipeline(pipeline_id):
    """Retrieves a single pipeline document."""
    doc = db.collection('pipelines').document(pipeline_id).get()
    if not doc.exists:
        return 'Pipeline not found.', 404
    return doc.to_dict(), 200

def list_pipelines(request):
    """Lists all pipeline documents."""
    pipelines = []
    for doc in db.collection('pipelines').stream():
        pipelines.append(doc.to_dict())
    return {"pipelines": pipelines}, 200

def update_pipeline(request, pipeline_id):
    """Updates an existing pipeline document."""
    # (Implementation for updating a pipeline would go here)
    # For now, we'll just return a placeholder.
    return 'Update functionality not yet implemented.', 501

def delete_pipeline(pipeline_id):
    """Deletes a pipeline document."""
    db.collection('pipelines').document(pipeline_id).delete()
    return '', 204
