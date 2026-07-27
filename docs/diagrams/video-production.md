# Video Production & Transcoding Pipeline Sequence Diagram

This document illustrates the core video production workflow, including media upload, automated multi-resolution video transcoding (360p to 4K), audio track extraction, and job execution management.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Content Producer"
    participant Frontend as "Next.js Frontend"
    participant API as "FastAPI Gateway (/api/v1/media)"
    participant Storage as "Cloud Storage (GCS)"
    participant PubSub as "GCP Pub/Sub"
    participant Worker as "Unified Media Transcoder Worker"
    participant TranscoderAPI as "GCP Video Transcoder API / FFmpeg"
    participant DB as "Firestore DB"

    User->>Frontend: Select Source Video & Encoding Preset (Resolution, Bitrate, Audio Format)
    Frontend->>API: POST /api/v1/media/upload-url (Filename, Content-Type)
    API-->>Frontend: Signed Upload URL & Video ID

    Frontend->>Storage: Direct Upload Video Binary (PUT signed URL)
    Storage-->>Frontend: Upload 200 OK

    Frontend->>API: POST /api/v1/media/jobs (Video ID, Presets, CRF, Audio Extraction)
    API->>DB: Write Job Record (Status: SUBMITTED)
    API->>PubSub: Publish Media Processing Task
    API-->>Frontend: Return Job Metadata (201 Created)

    PubSub->>Worker: Consume Task Message
    Worker->>DB: Update Status (Status: PROCESSING, Progress: 10%)
    
    alt GCP Cloud Transcoder Service Enabled
        Worker->>TranscoderAPI: Submit Job Spec (HLS/DASH, Resolutions, Bitrates)
        TranscoderAPI-->>Worker: Transcode Progress & Completion Callback
    else Local FFmpeg Execution
        Worker->>TranscoderAPI: Execute FFmpeg Multi-pass Transcode Pipeline
        TranscoderAPI-->>Worker: Output Transcoded Renditions & Extracted Audio Tracks
    end

    Worker->>Storage: Upload Processed Renditions (360p, 720p, 1080p, audio.mp3)
    Storage-->>Worker: GCS Rendition URIs
    Worker->>DB: Update Job Record (Status: COMPLETED, Outputs, Duration, Filesizes)

    Frontend->>API: GET /api/v1/media/jobs/{id}
    API->>DB: Query Job Data
    DB-->>API: Job Execution Details
    API-->>Frontend: Return Video Rendition Links & Metadata
    Frontend-->>User: Render Video Player with Rendition Selector
```

## Key Technical Steps

1. **Direct-to-GCS Upload**: Bypasses backend API bottleneck by generating signed GCS URLs for fast uploads.
2. **Asynchronous Task Queue**: Uses Pub/Sub messaging for worker decoupling and load distribution.
3. **Multi-Rendition Output**: Generates multiple bitrate renditions and isolated audio streams in parallel.
