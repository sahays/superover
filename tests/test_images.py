import pytest
from fastapi.testclient import TestClient
from api.main import app
from libs.database import get_db, ImageJobStatus
import uuid

client = TestClient(app)

@pytest.fixture
def mock_asset():
    db = get_db()
    asset_id = f"test-asset-{uuid.uuid4()}"
    db.create_video(
        video_id=asset_id,
        filename="test.jpg",
        gcs_path="gs://test/test.jpg",
        content_type="image/jpeg",
        size_bytes=1024
    )
    return asset_id

@pytest.fixture
def mock_prompt():
    db = get_db()
    prompt = db.create_prompt(
        name="Test Adapt",
        type="image_adaptation",
        prompt_text="Generate vertical version"
    )
    return prompt["prompt_id"]

def test_create_image_job(mock_asset, mock_prompt):
    payload = {
        "video_id": mock_asset,
        "prompt_id": mock_prompt,
        "config": {
            "aspect_ratios": ["16:9", "9:16"],
            "resolution": "HD"
        }
    }
    response = client.post("/api/images/jobs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["video_id"] == mock_asset
    assert "16:9" in data["config"]["aspect_ratios"]

def test_get_image_job(mock_asset, mock_prompt):
    # Create first
    payload = {
        "video_id": mock_asset,
        "prompt_id": mock_prompt,
        "config": {"aspect_ratios": ["1:1"], "resolution": "HD"}
    }
    create_res = client.post("/api/images/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    
    # Get
    response = client.get(f"/api/images/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id

def test_list_jobs_for_asset(mock_asset, mock_prompt):
    client.post("/api/images/jobs", json={
        "video_id": mock_asset,
        "prompt_id": mock_prompt,
        "config": {"aspect_ratios": ["1:1"], "resolution": "HD"}
    })
    
    response = client.get(f"/api/images/jobs/asset/{mock_asset}")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_get_signed_url():
    response = client.post("/api/images/signed-url", params={"gcs_path": "gs://test/img.jpg"})
    assert response.status_code == 200
    assert "url" in response.json()
    assert "storage.googleapis.com" in response.json()["url"]
