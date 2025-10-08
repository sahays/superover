# Architecture Overview

## System Design

Super Over Alchemy is a modular video analysis system designed to run locally or on Google Cloud Run with minimal changes.

### Core Principles

1. **Modular Design**: Each component is independent and reusable
2. **Cloud-Native**: Uses GCP services (GCS, Firestore) from the start
3. **Local-First**: Fully functional on localhost for development
4. **Stateless Workers**: All state in Firestore, not in memory
5. **Scalable**: Easy to add more workers or deploy to Cloud Run

## Component Architecture

```
┌─────────────┐
│   Browser   │
│  (Future)   │
└──────┬──────┘
       │
       │ HTTP
       ▼
┌─────────────────────────────────────┐
│         FastAPI Server              │
│  ┌──────────────────────────────┐  │
│  │   Routes                     │  │
│  │   - /api/videos/*            │  │
│  │   - /api/tasks/*             │  │
│  └──────────────────────────────┘  │
└─────────┬───────────────────────────┘
          │
          │ Firestore
          ▼
    ┌─────────────┐        ┌──────────────┐
    │  Firestore  │◄───────┤    Worker    │
    │  Database   │        │   Process    │
    │             │        │              │
    │  - videos   │        │ Polls tasks  │
    │  - tasks    │        │ Processes    │
    │  - manifests│        │ video files  │
    │  - results  │        └──────┬───────┘
    └─────────────┘               │
          ▲                       │
          │                       │
          │                       ▼
          │              ┌─────────────────┐
          │              │  Video Libs     │
          │              │  - compress     │
          │              │  - chunk        │
          │              │  - extract_audio│
          │              │  - metadata     │
          │              └────────┬────────┘
          │                       │
          │                       ▼
          │              ┌─────────────────┐
          │              │   Gemini API    │
          │              │   - scene       │
          │              │   - objects     │
          │              │   - transcribe  │
          │              │   - moderate    │
          │              └─────────────────┘
          │
          ▼
   ┌──────────────────┐
   │  Google Cloud    │
   │    Storage       │
   │                  │
   │  - uploads/      │
   │  - processed/    │
   │  - results/      │
   └──────────────────┘
```

## Data Flow

### Video Upload Flow

1. **Client** requests signed URL from API
2. **API** generates GCS signed URL, returns to client
3. **Client** uploads video directly to GCS (bypassing API)
4. **Client** notifies API of upload completion
5. **API** creates video record in Firestore

### Processing Flow

1. **Client** requests video processing via API
2. **API** creates processing task in Firestore
3. **Worker** polls Firestore, finds pending task
4. **Worker** downloads video from GCS to local temp
5. **Worker** processes video:
   - Extract metadata
   - Compress (optional)
   - Chunk into segments
   - Extract audio (optional)
6. **Worker** uploads processed files to GCS
7. **Worker** creates manifest in Firestore
8. **Worker** marks task complete
9. **Worker** updates video status to "processed"

### Analysis Flow

1. **Client** requests analysis via API
2. **API** creates analysis tasks (one per chunk per analysis type)
3. **Worker** polls Firestore, finds analysis task
4. **Worker** downloads chunk from GCS
5. **Worker** calls Gemini API with video chunk
6. **Worker** saves results to Firestore
7. **Worker** marks task complete
8. When all tasks complete, video status → "completed"

## Database Schema

### Firestore Collections

#### `videos` Collection
```javascript
{
  video_id: string,          // Unique identifier
  filename: string,          // Original filename
  gcs_path: string,          // gs://bucket/path
  content_type: string,      // video/mp4
  size_bytes: number,
  status: enum,              // uploaded|processing|processed|analyzing|completed|failed
  created_at: timestamp,
  updated_at: timestamp,
  metadata: object,          // Custom metadata
  error_message: string      // If failed
}
```

#### `manifests` Collection
```javascript
{
  video_id: string,
  version: string,           // "1.0"
  created_at: timestamp,
  original: {
    format: string,
    duration: number,
    size_bytes: number,
    video: {...},
    audio: {...}
  },
  compressed: {
    gcs_path: string
  },
  chunks: {
    count: number,
    duration_per_chunk: number,
    items: [
      {
        index: number,
        filename: string,
        gcs_path: string,
        start_time: number,
        end_time: number,
        duration: number,
        size_bytes: number
      }
    ]
  },
  audio: {
    gcs_path: string,
    format: string
  }
}
```

#### `analysis_tasks` Collection
```javascript
{
  task_id: string,
  video_id: string,
  task_type: string,         // video_processing|analysis_scene|analysis_objects|...
  status: enum,              // pending|processing|completed|failed
  input_data: object,        // Task-specific input
  result_data: object,       // Task results
  created_at: timestamp,
  updated_at: timestamp,
  error_message: string
}
```

#### `results` Collection
```javascript
{
  video_id: string,
  result_type: string,       // scene|objects|transcription|moderation
  result_data: object,       // Analysis results
  gcs_path: string,          // Optional full result file
  created_at: timestamp
}
```

## API Endpoints

### Videos

- `POST /api/videos/signed-url` - Get signed upload URL
- `POST /api/videos` - Create video record
- `GET /api/videos/{id}` - Get video info
- `GET /api/videos` - List videos
- `POST /api/videos/{id}/process` - Start processing
- `POST /api/videos/{id}/analyze` - Start analysis
- `GET /api/videos/{id}/manifest` - Get processing manifest
- `GET /api/videos/{id}/results` - Get analysis results

### Tasks

- `GET /api/tasks/{id}` - Get task info
- `GET /api/tasks/video/{video_id}` - List tasks for video
- `GET /api/tasks` - List pending tasks (for workers)

## Storage Layout

### GCS Buckets

```
uploads/
  └── {video_id}.mp4           # Original uploaded videos

processed/
  └── {video_id}/
      ├── compressed.mp4        # Compressed version
      ├── chunks/
      │   ├── chunk_0000.mp4
      │   ├── chunk_0001.mp4
      │   └── ...
      └── audio.mp3             # Extracted audio

results/
  └── {video_id}/
      ├── scene_analysis.json
      ├── objects.json
      ├── transcription.json
      └── moderation.json
```

## Deployment Models

### Local Development

```
┌──────────────┐     ┌──────────────┐
│  Terminal 1  │     │  Terminal 2  │
│              │     │              │
│  API Server  │     │    Worker    │
│  (uvicorn)   │     │   (python)   │
└──────┬───────┘     └──────┬───────┘
       │                    │
       │      GCP Cloud     │
       ▼                    ▼
   ┌─────────────────────────────┐
   │  Firestore + GCS + Gemini   │
   └─────────────────────────────┘
```

### Cloud Run Deployment

```
┌─────────────────┐      ┌─────────────────┐
│  Cloud Run      │      │  Cloud Run      │
│  API Service    │      │  Worker Service │
│  (public)       │      │  (private)      │
│                 │      │  min_instances=1│
└────────┬────────┘      └────────┬────────┘
         │                        │
         │    Firestore + GCS     │
         ▼                        ▼
    ┌──────────────────────────────────┐
    │  Firestore + GCS + Gemini API    │
    └──────────────────────────────────┘
```

## Scalability

### Horizontal Scaling

- **API**: Add more Cloud Run instances (auto-scales with traffic)
- **Workers**: Increase `min_instances` or deploy multiple worker services
- **Database**: Firestore auto-scales
- **Storage**: GCS auto-scales

### Vertical Scaling

- **Memory**: Increase container memory for larger videos
- **CPU**: Add more CPU for faster processing
- **Concurrency**: Increase `max_concurrent_tasks` in worker

### Cost Optimization

- **Local Dev**: Free (uses free tiers of GCS, Firestore, Gemini)
- **Cloud Run**: Pay only when processing (API idle cost ~$0)
- **Worker**: Set `min_instances=0` if not constantly processing
- **Storage**: Lifecycle policies to delete old temp files

## Security Considerations

### Authentication

- **Local**: Uses gcloud application-default credentials
- **Cloud Run**: Uses service account credentials
- **API**: Can add API keys or OAuth later

### Authorization

- **GCS**: Signed URLs expire in 15 minutes
- **Firestore**: Service account has full access
- **Gemini**: API key in environment variables

### Data Privacy

- Videos stored in private GCS buckets
- Results only accessible via API
- Can add encryption at rest/in transit

## Future Enhancements

1. **Frontend**: React/Next.js UI for uploads and viewing results
2. **Webhooks**: Notify client when processing complete
3. **Batch Processing**: Process multiple videos in parallel
4. **Result Caching**: Cache common analysis results
5. **Custom Models**: Support custom ML models beyond Gemini
6. **Live Streaming**: Process live video streams
7. **Collaboration**: Multi-user support with auth
