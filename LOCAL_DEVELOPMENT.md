# Local Development Guide

This guide explains how to run the Super Over Alchemy application locally for development.

## Prerequisites

- Python 3.9+
- Node.js 18+
- Google Cloud SDK (`gcloud` CLI)
- GCP credentials configured (`gcloud auth application-default login`)

## Running the API Service Locally

The API service needs to run on port 8000:

```bash
cd services/api_service
./run-local.sh
```

This will:
1. Create a Python virtual environment (if needed)
2. Install dependencies
3. Load environment variables from `.env`
4. Start the FastAPI server on `http://localhost:8000`

**API Documentation:** http://localhost:8000/docs

### What the API service needs:

- **GCP Project Access:** Make sure you're authenticated with `gcloud auth application-default login`
- **Environment Variables:** Loaded from project root `.env` file
  - `GCP_PROJECT_ID`
  - `RAW_UPLOADS_BUCKET_NAME`
  - `JOBS_TOPIC_ID`

### Testing the API:

```bash
# Health check
curl http://localhost:8000/health

# Root endpoint
curl http://localhost:8000/
```

## Running the Frontend Locally

The frontend runs on port 3000:

```bash
cd frontend
npm run dev
```

This will start Next.js development server on `http://localhost:3000`

### Frontend Configuration:

The frontend is configured in `frontend/.env.local`:

```bash
# For local development (API on localhost)
NEXT_PUBLIC_API_URL=http://localhost:8000

# For production API (uncomment to use deployed service)
# NEXT_PUBLIC_API_URL=https://api-service-p2irpfu5ya-el.a.run.app
```

**Important:** Restart the frontend dev server (`npm run dev`) after changing `.env.local`

## Complete Local Setup

### Terminal 1 - API Service:
```bash
cd services/api_service
./run-local.sh
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

### Terminal 3 - Testing:
```bash
# Open in browser
open http://localhost:3000
```

## Testing the Scene Analyzer

1. Navigate to http://localhost:3000 (redirects to `/scene-analyzer`)
2. Click "Create New Analysis"
3. Select a video file
4. Click "Create & Upload"
5. Watch the progress bar as the file uploads
6. The job should appear in the list with "queued" status
7. The Cloud Run Job worker will process it (deployed in GCP)

## Troubleshooting

### "Failed to create job: Network Error"

- **Cause:** API service not running or wrong URL
- **Fix:** Make sure API service is running on port 8000
- **Check:** `curl http://localhost:8000/health`

### "CORS Error"

- **Cause:** Frontend trying to use production API
- **Fix:** Update `frontend/.env.local` to use `http://localhost:8000`
- **Restart:** Stop and restart frontend dev server

### "Module not found" in API service

- **Cause:** Dependencies not installed
- **Fix:** Delete `venv` folder and run `./run-local.sh` again

### "GCP Authentication Error"

- **Cause:** Not authenticated with GCP
- **Fix:** Run `gcloud auth application-default login`

### Job stays in "queued" status

- **Cause:** Worker is deployed in GCP, not running locally
- **Check Worker Logs:**
  ```bash
  gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=scene-analyzer-worker" --limit 50 --project=search-and-reco
  ```

## Development Workflow

### 1. Frontend Changes
- Edit files in `frontend/src`
- Hot reload automatically updates browser
- No need to restart dev server

### 2. API Service Changes
- Edit files in `services/api_service`
- Uvicorn will auto-reload on file changes
- Check logs in the terminal

### 3. Testing End-to-End
- Use the frontend to upload a video
- Monitor API service logs in terminal 1
- Check Firestore for job status:
  ```bash
  # In browser, go to:
  # https://console.firebase.google.com/project/search-and-reco/firestore/databases/-default-/data/~2FsceneAnalysisJobs
  ```

## Building for Production

### Build Frontend:
```bash
cd frontend
npm run build
```

### Build and Deploy API:
```bash
./scripts/build-and-push.sh --service api-service
./scripts/deploy.sh --service api-service
```

### Build and Deploy Worker:
```bash
./scripts/build-and-push.sh --service scene-analyzer-worker
# Jobs are triggered automatically via Pub/Sub
```

## Environment Variables Reference

### Project Root `.env`:
```bash
GCP_PROJECT_ID="search-and-reco"
GCP_REGION="asia-south1"
RAW_UPLOADS_BUCKET_NAME="alchemy-super-over-inputs"
PROCESSED_OUTPUTS_BUCKET_NAME="alchemy-super-over-outputs"
JOBS_TOPIC_ID="scene-analysis-jobs"
```

### Frontend `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000  # or production URL
```

## Quick Commands

```bash
# Start everything locally
cd services/api_service && ./run-local.sh &
cd frontend && npm run dev

# Check API health
curl http://localhost:8000/health

# View recent logs from Cloud Run Job worker
gcloud logging read "resource.type=cloud_run_job" --limit=20 --project=search-and-reco

# View Firestore jobs
gcloud firestore documents list sceneAnalysisJobs --project=search-and-reco

# Deploy everything
./scripts/build-and-push.sh
./scripts/deploy.sh
```

## Architecture

```
┌─────────────────┐
│   Frontend      │  http://localhost:3000
│   (Next.js)     │  User uploads video
└────────┬────────┘
         │ HTTP POST
         ▼
┌─────────────────┐
│   API Service   │  http://localhost:8000
│   (FastAPI)     │  Generates signed URL, creates job
└────────┬────────┘
         │ 1. Upload to GCS
         │ 2. Publish to Pub/Sub
         ▼
┌─────────────────┐
│   Cloud Pub/Sub │  (Deployed in GCP)
│   Topic         │  scene-analysis-jobs
└────────┬────────┘
         │ Push subscription
         ▼
┌─────────────────┐
│  Scene Analyzer │  (Deployed as Cloud Run Job)
│  Worker         │  Processes video, writes results
└─────────────────┘
```

## Notes

- The **worker** always runs in GCP (Cloud Run Job), not locally
- The **API service** and **frontend** run locally for development
- Jobs are stored in **Firestore** and visible from local frontend
- Video files are stored in **GCS** buckets in GCP
