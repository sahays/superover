import pytest
from fastapi.testclient import TestClient
from api.main import app
from libs.database import get_db
import uuid


@pytest.fixture()
def client():
    """TestClient — seeding is suppressed by conftest._no_seed."""
    return TestClient(app)


@pytest.fixture
def mock_asset():
    db = get_db()
    asset_id = f"test-asset-{uuid.uuid4()}"
    db.create_video(
        video_id=asset_id,
        filename="test.jpg",
        gcs_path="gs://test/test.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
    )
    yield asset_id
    # Cleanup
    db.videos.document(asset_id).delete()


@pytest.fixture
def mock_prompt():
    db = get_db()
    prompt = db.create_prompt(
        name="Test Adapt",
        type="image_adaptation",
        prompt_text="Generate vertical version",
    )
    prompt_id = prompt["prompt_id"]
    yield prompt_id
    # Cleanup
    db.delete_prompt(prompt_id)


def _cleanup_image_jobs(db, video_id):
    """Delete all image jobs and their results for a test asset."""
    jobs = db.list_image_jobs_for_video(video_id)
    for job in jobs:
        job_id = job["job_id"]
        for doc in db.image_results.where("job_id", "==", job_id).stream():
            doc.reference.delete()
        db.image_jobs.document(job_id).delete()


def test_create_image_job(client, mock_asset, mock_prompt):
    payload = {
        "video_id": mock_asset,
        "prompt_id": mock_prompt,
        "config": {"aspect_ratios": ["16:9", "9:16"], "resolution": "HD"},
    }
    response = client.post("/api/images/jobs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["video_id"] == mock_asset
    assert "16:9" in data["config"]["aspect_ratios"]

    _cleanup_image_jobs(get_db(), mock_asset)


def test_get_image_job(client, mock_asset, mock_prompt):
    payload = {
        "video_id": mock_asset,
        "prompt_id": mock_prompt,
        "config": {"aspect_ratios": ["1:1"], "resolution": "HD"},
    }
    create_res = client.post("/api/images/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    response = client.get(f"/api/images/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id

    _cleanup_image_jobs(get_db(), mock_asset)


def test_list_jobs_for_asset(client, mock_asset, mock_prompt):
    client.post(
        "/api/images/jobs",
        json={
            "video_id": mock_asset,
            "prompt_id": mock_prompt,
            "config": {"aspect_ratios": ["1:1"], "resolution": "HD"},
        },
    )

    response = client.get(f"/api/images/jobs/asset/{mock_asset}")
    assert response.status_code == 200
    assert len(response.json()) >= 1

    _cleanup_image_jobs(get_db(), mock_asset)


def test_get_signed_url(client):
    response = client.post("/api/images/signed-url", params={"gcs_path": "gs://test/img.jpg"})
    assert response.status_code == 200
    assert "url" in response.json()
    assert "storage.googleapis.com" in response.json()["url"]
