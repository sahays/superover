# Video Reframing & Dynamic Crop Sequence Diagram

This diagram details the sequence flow for intelligent video reframing, where horizontal (16:9) video content is automatically cropped and reframed into vertical (9:16) or square (1:1) compositions while tracking subject movement and action.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Client / Creator"
    participant Frontend as "Next.js Frontend"
    participant API as "FastAPI Gateway (/api/v1/media)"
    participant PubSub as "GCP Pub/Sub (media-jobs)"
    participant Worker as "Media Worker (unified_worker)"
    participant Gemini as "Gemini Scene Analysis Engine"
    participant Transcoder as "Transcoder Engine (FFmpeg / GCP Transcoder)"
    participant Storage as "Cloud Storage (GCS)"
    participant DB as "Firestore DB"

    User->>Frontend: Select Video & Request Reframing (e.g. 16:9 -> 9:16)
    Frontend->>API: POST /api/v1/media/reframe (Video ID, Target Aspect Ratio)
    API->>DB: Create Reframe Job (Status: PENDING)
    API->>PubSub: Publish Reframe Job Event
    API-->>Frontend: Return Job ID (202 Accepted)

    PubSub->>Worker: Pull Reframe Job Event
    Worker->>Storage: Read Input Video
    Storage-->>Worker: Download Video Chunk / File

    Worker->>Gemini: Analyze Saliency & Subject Motion Trajectory
    Note over Gemini: Tracks key person / action coordinates<br/>Outputs frame-by-frame focus bounding boxes
    Gemini-->>Worker: Return Tracking Keyframes & Crop Bounding Boxes

    Worker->>Transcoder: Construct Dynamic FFmpeg Crop Filter Pipeline
    Note over Transcoder: Applies smooth pan & scan crop filters<br/>Transcodes to target resolution (e.g. 1080x1920)
    Transcoder-->>Worker: Transcoded Video File

    Worker->>Storage: Upload Reframed Video
    Storage-->>Worker: Return GCS URI
    Worker->>DB: Update Job Status (COMPLETED, Output URI, Metrics)
    
    Frontend->>API: Poll GET /api/v1/media/jobs/{id}
    API->>DB: Query Job Status
    DB-->>API: Job Details (COMPLETED)
    API-->>Frontend: Return Reframed Video URL
    Frontend-->>User: Preview Reframed Video Player
```

## Key Technical Steps

1. **Subject Detection & Motion Tracking**: Uses Gemini scene analysis to detect action centroids frame-by-frame.
2. **Crop Filter Synthesis**: Synthesizes smooth dynamic panning coordinates (`crop=w:h:x:y`) to prevent camera jitter.
3. **Hardware Acceleration**: Executes FFmpeg transcoding via worker infrastructure to output multi-format deliverables.
