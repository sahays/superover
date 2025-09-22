# Super Over Alchemy

**Super Over Alchemy** is a Gemini-powered narrative analytics platform designed for cloud-native, event-driven video
processing. The system deconstructs video content scene-by-scene to analyze characters, dialogue, emotional tone, and
more, providing data-driven insights for creative decision-making.

This project is structured as a pipeline of independent microservices, each packaged as a container and designed to be
deployed on Google Cloud Run.

---

## System Architecture

The system is a collection of serverless microservices that communicate via Google Cloud Storage (GCS) events,
orchestrated by Eventarc.

**Workflow:**

1.  A video is uploaded to a GCS bucket.
2.  An Eventarc trigger invokes the **`video-processor-service`**, which chunks the video into manageable segments and
    writes them back to GCS.
3.  The creation of these chunks (and a manifest file) triggers the **`audio_extractor`** and **`scene_analyzer`**
    services.
4.  Each service processes its input and writes its output (e.g., extracted audio, JSON analysis) to a designated GCS
    path.

This decoupled architecture allows for flexible, scalable, and independent processing of media files.

### Core Services (Modules)

| Service Name          | Purpose                                                  | Input Trigger       | Primary Output(s)                           |
| :-------------------- | :------------------------------------------------------- | :------------------ | :------------------------------------------ |
| **`media-inspector`** | 🔍 Reads the technical metadata of a media file.         | GCS file upload     | A `_metadata.json` file.                    |
| **`audio-extractor`** | 🎵 Extracts audio channels from a video file.            | GCS file upload     | FLAC audio files for each channel.          |
| **`video-processor`** | 📼 Chunks a video file into smaller segments.            | GCS file upload     | Segmented `.mp4` files and a manifest.      |
| **`scene-analyzer`**  | ✨ Analyzes a video chunk with Gemini for rich metadata. | GCS manifest upload | A detailed `_analysis.json` for each chunk. |

---

## Cloud Deployment with Pub/Sub and Cloud Run

This project is designed as a pipeline of event-driven services orchestrated by Pub/Sub and deployed on Cloud Run. This
architecture provides scalability, reliability, and control over concurrency.

### Prerequisites

1.  Enable the Cloud Run, Cloud Build, Artifact Registry, and Pub/Sub APIs.
2.  Authenticate Docker: `gcloud auth configure-docker <region>-docker.pkg.dev`
3.  Create an Artifact Registry repo:
    `gcloud artifacts repositories create <repo-name> --repository-format=docker --location=<region>`
4.  Create a Service Account for Pub/Sub push subscriptions:
    ```bash
    gcloud iam service-accounts create pubsub-invoker --display-name "Pub/Sub Cloud Run Invoker"
    ```

### Deployment Workflow

The workflow involves creating Pub/Sub topics, deploying the services, and then creating push subscriptions to connect
them.

#### Step 1: Create Pub/Sub Topics

You need topics to act as message queues between services.

```bash
# Topic for initial video uploads
gcloud pubsub topics create raw-video-uploads

# Topic for when the video processor finishes and creates a manifest
gcloud pubsub topics create video-processing-complete
```

#### Step 2: Deploy a Service

Deploy each module as a separate, private Cloud Run service.

```bash
# Example for the video-processor service
gcloud run deploy video-processor-service \
  --source . \
  --region <your-region> \
  --timeout=3600 \ # Set timeout (e.g., 60 minutes) for long-running jobs
  --max-instances=10 \ # Control max concurrency to protect downstream APIs
  --no-allow-unauthenticated \
  --set-env-vars="CHUNK_DURATION=60"
```

- `--timeout`: Crucial for long jobs. Max is 3600.
- `--max-instances`: Controls concurrency and cost.
- `--no-allow-unauthenticated`: The service will be private and can only be invoked by an authenticated entity, like our
  Pub/Sub subscription.

Repeat this command for the other services (`audio-extractor-service`, `scene-analyzer-service`, etc.).

#### Step 3: Create Push Subscriptions

A push subscription connects a topic to a service. When a message is published to the topic, Pub/Sub pushes it to the
service's HTTPS endpoint.

1.  **Get the URL of your deployed service:**

    ```bash
    gcloud run services describe video-processor-service --format 'value(status.url)'
    ```

2.  **Create the subscription:**
    ```bash
    # Subscription to connect the 'raw-video-uploads' topic to the 'video-processor-service'
    gcloud pubsub subscriptions create video-processor-sub \
      --topic raw-video-uploads \
      --push-endpoint=<URL_OF_YOUR_VIDEO_PROCESSOR_SERVICE> \
      --push-auth-service-account=pubsub-invoker@<YOUR_PROJECT_ID>.iam.gserviceaccount.com
    ```

#### Step 4: Configure GCS Triggers

Finally, configure your GCS bucket to send notifications to the appropriate Pub/Sub topic.

```bash
# Configure the raw uploads bucket
gcloud storage buckets notifications create gs://<your-raw-videos-bucket> \
  --topic=raw-video-uploads \
  --event-types=OBJECT_FINALIZE

# You can also set up a trigger for the processed bucket to notify the scene-analyzer
gcloud storage buckets notifications create gs://<your-processed-output-bucket> \
  --topic=video-processing-complete \
  --event-types=OBJECT_FINALIZE \
  --path-filter=_report.json # Only trigger for the manifest file
```

Now, when you upload a video to `gs://<your-raw-videos-bucket>`, the entire pipeline will be triggered.

---

## Internal Design Documents

For more detailed technical designs of each module's core logic, please see the Low-Level Design (LLD) documents:

- [Media Inspector LLD](./docs/media_inspector_lld.md)
- [Audio Extractor LLD](./docs/audio_extractor_lld.md)
- [Video Processor LLD](./docs/video_processor_lld.md)
- [Scene Analyzer LLD](./docs/scene_analyzer_lld.md)
