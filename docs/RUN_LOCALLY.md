# Running Super Over Alchemy Locally

Complete guide to run the entire system on your local machine.

## Quick Start (3 Terminals)

### Terminal 1: API Server
```bash
# Activate Python virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run the API
python api/main.py
```

API will be available at `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

### Terminal 2: Worker
```bash
# Activate Python virtual environment
source venv/bin/activate

# Run the worker
python workers/video_worker.py
```

### Terminal 3: Frontend
```bash
# Go to frontend directory
cd frontend

# Install dependencies (first time only)
npm install

# Run development server
npm run dev
```

Frontend will be available at `http://localhost:3000`

## Testing the Complete Flow

1. **Open frontend** at `http://localhost:3000`

2. **Upload a video**:
   - Click "Upload Video" button
   - Select a video file (recommend starting with a small one, < 50MB)
   - Click "Upload and Process"

3. **Watch the progress**:
   - Upload happens directly to GCS
   - Worker automatically picks up the processing task
   - Watch Terminal 2 for processing logs

4. **View results**:
   - Once status is "Processed", click on the video card
   - Click "Start Analysis" to run Gemini analysis
   - Wait for analysis to complete
   - View results on the detail page

## Architecture (Local Setup)

```
Browser (localhost:3000)
    ↓
Next.js Frontend
    ↓
FastAPI (localhost:8000)
    ↓ ↓
   GCS + Firestore (Cloud)
    ↓
Worker (Python process)
    ↓
Gemini API (Cloud)
```

## Troubleshooting

### API won't start
- Check `.env` file has all required values
- Run `gcloud auth application-default login`
- Check port 8000 is not in use: `lsof -i :8000`

### Worker not processing
- Check worker logs for errors
- Verify Firestore database exists
- Check GCS buckets exist
- Verify worker is running: look for "Video Processing Worker Started"

### Frontend errors
- Run `npm install` in frontend directory
- Check `.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Check API is running at `http://localhost:8000`

### Upload fails
- Check browser console for errors
- Verify GCS buckets exist: `gsutil ls`
- Check API logs in Terminal 1

### Processing stuck
- Check worker logs in Terminal 2
- Verify `ffmpeg` is installed: `ffmpeg -version`
- Check GCS bucket permissions

## Monitoring

### Check API Health
```bash
curl http://localhost:8000/health
```

### List Videos
```bash
curl http://localhost:8000/api/videos
```

### Check Specific Video
```bash
curl http://localhost:8000/api/videos/<video_id>
```

### View Firestore Data
- Go to [Firebase Console](https://console.firebase.google.com/)
- Select your project
- Click "Firestore Database"
- Browse collections: videos, manifests, analysis_tasks, results

### View GCS Files
```bash
# List uploaded videos
gsutil ls gs://your-project-id-uploads/

# List processed files
gsutil ls gs://your-project-id-processed/
```

## Development Tips

### Hot Reload
- **Frontend**: Automatically reloads on file changes
- **API**: Run with `uvicorn api.main:app --reload`
- **Worker**: Restart manually after code changes

### Debugging
- **Frontend**: Use browser DevTools Console and Network tab
- **API**: Check Terminal 1 for logs
- **Worker**: Check Terminal 2 for logs

### Testing with Small Videos
For faster testing, use short videos:
- 10-30 seconds
- < 50MB
- Common formats: MP4, MOV

### Clear All Data
```bash
# Delete all videos from GCS
gsutil -m rm -r gs://your-project-id-uploads/**
gsutil -m rm -r gs://your-project-id-processed/**

# Delete Firestore data
# Use Firebase Console or gcloud firestore delete command
```

## Next Steps

- Try different video formats
- Test with longer videos
- Explore analysis results
- Customize analysis types
- Add more features!
