# Quick Start Guide

Get Super Over Alchemy running locally in 10 minutes.

## Prerequisites Check

```bash
# Check Python
python --version  # Should be 3.9+

# Check ffmpeg
ffmpeg -version

# Check gcloud
gcloud --version

# Check Node.js (for frontend later)
node --version  # Should be 18+
```

If any are missing, see the installation section in README.md.

## 1. Setup GCP (5 minutes)

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Login to GCP
gcloud auth application-default login
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  storage.googleapis.com \
  firestore.googleapis.com

# Create GCS buckets
gsutil mb -l asia-south1 gs://${PROJECT_ID}-uploads
gsutil mb -l asia-south1 gs://${PROJECT_ID}-processed
gsutil mb -l asia-south1 gs://${PROJECT_ID}-results

# Create Firestore database
gcloud firestore databases create --location=asia-south1
```

## 2. Get Gemini API Key (2 minutes)

1. Visit https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key

## 3. Configure Application (1 minute)

```bash
# Copy example env file
cp .env.example .env

# Edit .env file with your values
nano .env  # or use your favorite editor
```

Required values in `.env`:
```bash
GCP_PROJECT_ID=your-project-id
UPLOADS_BUCKET=your-project-id-uploads
PROCESSED_BUCKET=your-project-id-processed
RESULTS_BUCKET=your-project-id-results
GEMINI_API_KEY=your-gemini-api-key-here
```

## 4. Install Dependencies (1 minute)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt
```

## 5. Start Services (1 minute)

**Terminal 1 - API Server:**
```bash
source venv/bin/activate
python api/main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2 - Worker:**
```bash
source venv/bin/activate
python workers/video_worker.py
```

You should see:
```
Video Processing Worker Started
Polling interval: 5s
```

## 6. Test It! (remainder of time)

Open a new terminal:

```bash
# Test health endpoint
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs  # macOS
# or visit http://localhost:8000/docs in your browser
```

### Upload a Test Video

1. Get a small test video (under 50MB recommended for first test)

2. Get signed URL:
```bash
curl -X POST http://localhost:8000/api/videos/signed-url \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.mp4",
    "content_type": "video/mp4"
  }' | jq
```

3. Copy the `signed_url` and `gcs_path` from the response

4. Upload your video:
```bash
curl -X PUT "<paste-signed-url-here>" \
  -H "Content-Type: video/mp4" \
  --data-binary @your-test-video.mp4
```

5. Create video record (replace `<gcs_path>` and adjust `size_bytes`):
```bash
curl -X POST http://localhost:8000/api/videos \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.mp4",
    "gcs_path": "<paste-gcs-path-here>",
    "content_type": "video/mp4",
    "size_bytes": 10485760
  }' | jq
```

6. Copy the `video_id` from response and start processing:
```bash
VIDEO_ID="<paste-video-id-here>"

curl -X POST http://localhost:8000/api/videos/$VIDEO_ID/process \
  -H "Content-Type: application/json" \
  -d '{
    "compress": true,
    "chunk": true,
    "extract_audio": true
  }' | jq
```

7. Watch the worker terminal - you should see processing logs!

8. Check status:
```bash
curl http://localhost:8000/api/videos/$VIDEO_ID | jq
```

9. Once status is "processed", start analysis:
```bash
curl -X POST http://localhost:8000/api/videos/$VIDEO_ID/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_types": ["scene", "objects", "transcription"]
  }' | jq
```

10. Get results (after analysis completes):
```bash
curl http://localhost:8000/api/videos/$VIDEO_ID/results | jq
```

## Troubleshooting

**"Permission denied" errors:**
```bash
gcloud auth application-default login
```

**"Bucket not found":**
```bash
# Verify buckets exist
gsutil ls
```

**"ffmpeg not found":**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

**Worker not processing:**
- Check worker logs for errors
- Verify Firestore database exists
- Check that video status is correct

## Next Steps

- Build the frontend (coming soon)
- Deploy to Cloud Run with `./deploy.sh`
- Try different analysis types
- Process longer videos

## Need Help?

- Check logs in both terminals
- Visit http://localhost:8000/docs for API documentation
- Check GCP Console for Firestore and GCS
