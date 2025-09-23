# Super Over Alchemy Terraform Infrastructure

This Terraform configuration deploys the complete Super Over Alchemy infrastructure on Google Cloud Platform.

## Prerequisites

1. **GCP Project**: Create a GCP project with billing enabled
2. **Terraform**: Install Terraform >= 1.0
3. **gcloud CLI**: Install and authenticate with `gcloud auth application-default login`
4. **Docker**: For building and pushing container images
5. **Gemini API Key**: Get your API key from Google AI Studio

## Quick Setup

1. **Configure variables**:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

2. **Initialize and deploy**:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

3. **Build and push container images**:
   ```bash
   # Configure Docker for Artifact Registry
   gcloud auth configure-docker <region>-docker.pkg.dev

   # Build and push each service
   ./scripts/build-and-push.sh
   ```

## Infrastructure Components

### Core Services
- **4x Cloud Run Services**: video-processor, audio-extractor, scene-analyzer, media-inspector
- **4x Pub/Sub Topics + Subscriptions**: Event-driven communication
- **2x Cloud Storage Buckets**: Raw videos and processed outputs
- **Artifact Registry**: Container image storage
- **Firestore**: Job and pipeline state storage
- **Service Accounts**: Secure access control

### Event Flow
1. Video uploaded to raw videos bucket
2. GCS notification → video-processor-jobs topic → video-processor service
3. Processed chunks trigger scene-analyzer and audio-extractor services
4. Results stored in processed outputs bucket

## Environment Variables

The system reads configuration from environment variables:

### Required
- `project_id`: Your GCP project ID
- `raw_videos_bucket_name`: Bucket for raw video uploads
- `processed_outputs_bucket_name`: Bucket for processed outputs
- `gemini_api_key`: Your Gemini API key

### Optional (with defaults)
- `region`: GCP region (default: us-central1)
- `chunk_duration`: Video chunk duration in seconds (default: 60)
- `gemini_model`: Gemini model version (default: models/gemini-1.5-pro-latest)

## Deployment Commands

```bash
# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Plan deployment
terraform plan

# Deploy infrastructure
terraform apply

# Destroy infrastructure
terraform destroy
```

## Container Image Management

After infrastructure deployment, you need to build and push container images:

```bash
# Get the Artifact Registry URL from Terraform output
REPO_URL=$(terraform output -raw artifact_registry_repository_url)

# Build and tag images for each service
docker build -t $REPO_URL/video-processor:latest .
docker build -t $REPO_URL/audio-extractor:latest .
docker build -t $REPO_URL/scene-analyzer:latest .
docker build -t $REPO_URL/media-inspector:latest .

# Push images
docker push $REPO_URL/video-processor:latest
docker push $REPO_URL/audio-extractor:latest
docker push $REPO_URL/scene-analyzer:latest
docker push $REPO_URL/media-inspector:latest
```

## Module Structure

```
terraform/
├── modules/
│   ├── cloud-run-service/     # Reusable Cloud Run service module
│   ├── pubsub-topic/          # Pub/Sub topic + subscription + IAM
│   ├── service-accounts/      # Service accounts and IAM roles
│   └── storage/               # GCS buckets + notifications
├── main.tf                    # Main infrastructure configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
└── terraform.tfvars.example   # Example configuration
```

## Security Features

- **Private Cloud Run services**: No public access, Pub/Sub authentication only
- **IAM least privilege**: Service accounts with minimal required permissions
- **Secure container images**: Images stored in private Artifact Registry
- **Firestore native mode**: ACID transactions and strong consistency

## Monitoring and Logs

- **Cloud Run logs**: Available in Cloud Logging
- **Pub/Sub metrics**: Monitor message flow and delivery
- **Storage notifications**: Track file upload events
- **Service health**: Cloud Run provides built-in health checks

## Troubleshooting

### Common Issues

1. **API not enabled**: Terraform automatically enables required APIs
2. **Permission denied**: Ensure your account has Project Editor role
3. **Container not found**: Build and push images after infrastructure deployment
4. **Pub/Sub delivery failures**: Check Cloud Run service logs for errors

### Useful Commands

```bash
# Check service status
gcloud run services list --region=<region>

# View service logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Test Pub/Sub message
gcloud pubsub topics publish video-processor-jobs --message='{"bucket":"test","name":"test.mp4"}'
```