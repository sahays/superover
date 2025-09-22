# Super Over Alchemy

**Super Over Alchemy** is a Gemini-powered narrative analytics platform designed for cloud-native, event-driven video processing. The system deconstructs video content scene-by-scene to analyze characters, dialogue, emotional tone, and more, providing data-driven insights for creative decision-making.

This project is structured as a pipeline of independent microservices, each packaged as a container and designed to be deployed on Google Cloud Run.

---

## System Architecture

The system is a collection of serverless microservices that communicate via Google Cloud Storage (GCS) events, orchestrated by Eventarc.

**Workflow:**
1.  A video is uploaded to a GCS bucket.
2.  An Eventarc trigger invokes the **`video-processor-service`**, which chunks the video into manageable segments and writes them back to GCS.
3.  The creation of these chunks (and a manifest file) triggers the **`audio_extractor`** and **`scene_analyzer`** services.
4.  Each service processes its input and writes its output (e.g., extracted audio, JSON analysis) to a designated GCS path.

This decoupled architecture allows for flexible, scalable, and independent processing of media files.

### Core Services (Modules)

| Service Name | Purpose | Input Trigger | Primary Output(s) |
| :--- | :--- | :--- | :--- |
| **`media-inspector`** | 🔍 Reads the technical metadata of a media file. | GCS file upload | A `_metadata.json` file. |
| **`audio-extractor`** | 🎵 Extracts audio channels from a video file. | GCS file upload | FLAC audio files for each channel. |
| **`video-processor`** | 📼 Chunks a video file into smaller segments. | GCS file upload | Segmented `.mp4` files and a manifest. |
| **`scene-analyzer`** | ✨ Analyzes a video chunk with Gemini for rich metadata. | GCS manifest upload | A detailed `_analysis.json` for each chunk. |

---

## Local Development and Testing

Each service can be run locally as a web server. Testing is done by sending a simulated GCS event payload using `curl`.

### 1. Run the Service Locally

Use `uvicorn` to start the web server for the module you want to test.

```bash
# Example for the video-processor
uvicorn video_processor.main:app --reload --port 8080
```
The `--reload` flag automatically restarts the server on code changes.

### 2. Simulate a GCS Event

In a separate terminal, use `curl` to send an HTTP POST request to your running service. The payload must mimic a CloudEvent from GCS.

**Steps:**
1.  Create a JSON file with the event data. For local file testing, this can just be a local path.
    ```json
    // Save as /tmp/event.json
    {
      "bucket": "local-bucket",
      "name": "inputs/your_test_video.mp4" 
    }
    ```
2.  Base64-encode this data.
    ```bash
    # On macOS
    BASE64_DATA=$(base64 -i /tmp/event.json)
    # On Linux
    BASE64_DATA=$(base64 -w 0 /tmp/event.json)
    ```
3.  Send the `curl` request.
    ```bash
    curl -X POST http://127.0.0.1:8080 \
      -H "Content-Type: application/json" \
      -d '{ "message": { "data": "'"$BASE64_DATA"'" } }'
    ```
4.  Observe the log output in your `uvicorn` terminal.

---

## Cloud Deployment on Google Cloud Run

Each service is deployed from the project root as a separate Cloud Run instance.

### Prerequisites
1.  Enable the Cloud Run, Cloud Build, and Artifact Registry APIs.
2.  Authenticate Docker: `gcloud auth configure-docker <region>-docker.pkg.dev`
3.  Create an Artifact Registry repo: `gcloud artifacts repositories create <repo-name> --repository-format=docker --location=<region>`

### Deploy a Service

The following command builds and deploys a service (e.g., `video-processor`). Run it from the project root.

```bash
gcloud run deploy video-processor-service \
  --source . \
  --region <your-region> \
  --set-env-vars="CHUNK_DURATION=60" \
  --allow-unauthenticated 
```
*   `--source .`: Builds the container from the current directory using the `Dockerfile`.
*   `--set-env-vars`: Sets environment variables to configure the service's behavior.
*   To redeploy, simply run the same command again after pushing your code changes.

### Connect Services with Eventarc

After deploying your services, create Eventarc triggers to connect them to GCS events.

```bash
# Example: Trigger for the video-processor when a file lands in a bucket
gcloud eventarc triggers create video-processor-trigger \
  --destination-run-service=video-processor-service \
  --destination-run-region=<your-region> \
  --location=<your-region> \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=<your-input-bucket-name>" \
  --service-account="<your-project-number>-compute@developer.gserviceaccount.com"
```
Repeat this process to create triggers for the other services, filtering on the specific output files they should respond to (e.g., `..._report.json` for the `scene-analyzer`).

---

## Internal Design Documents

For more detailed technical designs of each module's core logic, please see the Low-Level Design (LLD) documents:

- [Media Inspector LLD](./docs/media_inspector_lld.md)
- [Audio Extractor LLD](./docs/audio_extractor_lld.md)
- [Video Processor LLD](./docs/video_processor_lld.md)
- [Scene Analyzer LLD](./docs/scene_analyzer_lld.md)

```