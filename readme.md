# Super Over Alchemy

Video analysis and scene recognition system using Gemini AI.

## Features

- **Video Processing**: Automatic compression, chunking, and audio extraction
- **Scene Analysis**: AI-powered scene detection and description
- **Object Detection**: Identify and track objects throughout the video
- **Transcription**: Generate subtitles and speech-to-text
- **Content Moderation**: Automated content safety checking
- **Cloud-Native**: Designed to run locally or deploy to Google Cloud Run

## Architecture

- **API**: FastAPI REST API for video management
- **Worker**: Background processor for video processing and Gemini analysis
- **Storage**: Google Cloud Storage for video files
- **Database**: Cloud Firestore for metadata and state management
- **AI**: Google Gemini API for video analysis

## Local Development Setup

### Prerequisites

1. **Python 3.9+**
   ```bash
   python --version
   ```

2. **ffmpeg**
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # Verify
   ffmpeg -version
   ```

3. **Google Cloud SDK**
   ```bash
   # macOS
   brew install --cask google-cloud-sdk

   # Login and set project
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

4. **Node.js 18+ and npm** (for frontend)
   ```bash
   node --version
   npm --version
   ```

### GCP Setup

1. **Create GCP Project**
   ```bash
   export PROJECT_ID="your-project-id"
   gcloud config set project $PROJECT_ID
   ```

2. **Enable APIs**
   ```bash
   gcloud services enable \
     storage.googleapis.com \
     firestore.googleapis.com \
     aiplatform.googleapis.com
   ```

3. **Create GCS Buckets**
   ```bash
   gsutil mb -l asia-south1 gs://${PROJECT_ID}-uploads
   gsutil mb -l asia-south1 gs://${PROJECT_ID}-processed
   gsutil mb -l asia-south1 gs://${PROJECT_ID}-results
   ```

4. **Create Firestore Database**
   ```bash
   gcloud firestore databases create --location=asia-south1
   ```

5. **Get Gemini API Key**
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create an API key

### Application Setup

1. **Clone and setup**
   ```bash
   cd super-over-alchemy
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

   Example `.env`:
   ```bash
   GCP_PROJECT_ID=your-project-id
   GCP_REGION=asia-south1

   UPLOADS_BUCKET=your-project-id-uploads
   PROCESSED_BUCKET=your-project-id-processed
   RESULTS_BUCKET=your-project-id-results

   GEMINI_API_KEY=your-gemini-api-key
   GEMINI_MODEL=models/gemini-2.0-flash-exp

   ENVIRONMENT=local
   API_URL=http://localhost:8000
   FRONTEND_URL=http://localhost:3000
   ```

3. **Run the API**
   ```bash
   python api/main.py
   ```

   API will be available at `http://localhost:8000`
   - Swagger docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

4. **Run the Worker** (in a new terminal)
   ```bash
   source venv/bin/activate
   python workers/video_worker.py
   ```

## Usage

### Upload and Process a Video

1. **Get signed URL for upload**
   ```bash
   curl -X POST http://localhost:8000/api/videos/signed-url \
     -H "Content-Type: application/json" \
     -d '{
       "filename": "test.mp4",
       "content_type": "video/mp4"
     }'
   ```

2. **Upload video to GCS** (use signed URL from previous step)
   ```bash
   curl -X PUT "<signed_url>" \
     -H "Content-Type: video/mp4" \
     --data-binary @test.mp4
   ```

3. **Create video record**
   ```bash
   curl -X POST http://localhost:8000/api/videos \
     -H "Content-Type: application/json" \
     -d '{
       "filename": "test.mp4",
       "gcs_path": "<gcs_path from step 1>",
       "content_type": "video/mp4",
       "size_bytes": 1048576
     }'
   ```

4. **Start processing**
   ```bash
   curl -X POST http://localhost:8000/api/videos/<video_id>/process \
     -H "Content-Type: application/json" \
     -d '{
       "compress": true,
       "chunk": true,
       "extract_audio": true
     }'
   ```

5. **Check status**
   ```bash
   curl http://localhost:8000/api/videos/<video_id>
   ```

6. **Start analysis** (after processing is complete)
   ```bash
   curl -X POST http://localhost:8000/api/videos/<video_id>/analyze \
     -H "Content-Type: application/json" \
     -d '{
       "analysis_types": ["scene", "objects", "transcription", "moderation"]
     }'
   ```

7. **Get results**
   ```bash
   curl http://localhost:8000/api/videos/<video_id>/results
   ```

## Project Structure

```
super-over-alchemy/
├── api/                      # FastAPI application
│   ├── main.py              # Main application
│   ├── routes/              # API routes
│   │   ├── videos.py        # Video endpoints
│   │   └── tasks.py         # Task endpoints
│   └── models/              # Pydantic models
│       └── schemas.py
├── libs/                     # Reusable libraries
│   ├── storage.py           # GCS operations
│   ├── database.py          # Firestore operations
│   ├── video_processing/    # Video tools
│   │   ├── metadata.py
│   │   ├── compressor.py
│   │   ├── chunker.py
│   │   ├── audio.py
│   │   └── manifest.py
│   └── gemini/              # Gemini integration
│       └── analyzer.py
├── workers/                  # Background workers
│   └── video_worker.py      # Processing worker
├── frontend/                 # Next.js frontend (coming soon)
├── storage/                  # Local temp storage
│   └── temp/
├── config.py                 # Configuration
├── requirements.txt          # Python dependencies
├── .env.example             # Example environment file
└── README.md                # This file
```

## Deployment to Cloud Run

Coming soon...

## Contributing

This is a personal project. Feel free to fork and modify for your own use.

## License

MIT
