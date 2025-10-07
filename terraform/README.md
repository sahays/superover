# Super Over Alchemy - Infrastructure Setup

This directory contains Terraform configuration for deploying the Super Over Alchemy application to Google Cloud Platform.

## Quick Start

### Prerequisites
- Google Cloud SDK (`gcloud`) installed and authenticated
- Terraform >= 1.0 installed
- Project configured in `.env` file at project root
- Gemini API Key (for video analysis)

### Deployment Steps

1. **Initialize Terraform:**
   ```bash
   cd terraform
   terraform init
   ```

2. **Review planned changes:**
   ```bash
   terraform plan
   ```

3. **Apply infrastructure:**
   ```bash
   terraform apply
   ```

4. **Run post-configuration script:**
   ```bash
   cd ..
   ./scripts/configure-post-terraform.sh
   ```
   This script updates GCS bucket CORS with the actual Cloud Run service URLs.

5. **Build and deploy services:**
   ```bash
   ./scripts/build-and-push.sh
   ```

## Architecture

The infrastructure consists of:

### Core Services
- **frontend-service**: Next.js web application (Cloud Run)
- **api-service**: FastAPI backend (Cloud Run)
- **scene-analyzer-worker**: Video processing worker (Cloud Run Job)

### Storage
- **Raw Videos Bucket**: Stores uploaded videos with CORS enabled for direct browser uploads
- **Processed Outputs Bucket**: Stores analysis results

### Messaging
- **Pub/Sub Topic**: `scene-analysis-jobs` for job queueing
- **Push Subscription**: Triggers scene-analyzer-worker when new jobs are created

### Security
- **Service Account**: `super-over-services` with permissions for:
  - Cloud Storage (admin)
  - Firestore (user)
  - Pub/Sub (publisher/subscriber)
  - IAM Token Creator (for signed URLs)
- **Public Access**: API service allows public access for CORS preflight requests

## Configuration

All configuration is read from the root `.env` file:

```bash
# GCP Configuration
GCP_PROJECT_ID="your-project-id"
GCP_REGION="asia-south1"

# Storage
RAW_UPLOADS_BUCKET_NAME="alchemy-super-over-inputs"
PROCESSED_OUTPUTS_BUCKET_NAME="alchemy-super-over-outputs"

# Pub/Sub
JOBS_TOPIC_ID="scene-analysis-jobs"

# Gemini API
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="models/gemini-2.5-pro"
```

## Post-Deployment Configuration

The `scripts/configure-post-terraform.sh` script handles configuration that requires runtime information:

1. **GCS CORS Configuration**: Updates the raw uploads bucket with specific Cloud Run service URLs
   - Terraform creates the bucket with wildcard CORS (`*.run.app`)
   - Post-script updates it with the actual frontend URL for better security

**What it does:**
- Fetches the actual frontend-service URL from Cloud Run
- Updates GCS bucket CORS to allow that specific URL
- Also allows `localhost:3000` for local development

This approach ensures CORS works immediately after `terraform apply` (via wildcard), then tightens security with specific URLs.

## Manual Changes Captured in Terraform

The following manual configurations are now automated:

✅ **Service Account Permissions**
- Self-signing permission (`serviceAccountTokenCreator`) for GCS signed URLs

✅ **API Service Configuration**
- Public access enabled (required for CORS preflight requests from browsers)
- Environment variables including:
  - `GOOGLE_SERVICE_ACCOUNT_EMAIL` for signed URL generation
  - `FRONTEND_URL` dynamically set from frontend service output
  - `GCP_REGION` for constructing proper URLs

✅ **GCS CORS Configuration**
- Initial wildcard configuration in Terraform
- Specific URL configuration via post-script

✅ **Frontend Service URL**
- API service references frontend URL dynamically via Terraform outputs
- No hardcoded URLs in infrastructure code

## Service URL Construction

Cloud Run service URLs follow the format:
```
https://{service-name}-{project-number}.{region}.run.app
```

The build scripts (`scripts/build-and-push.sh`) automatically:
1. Fetch the project number at runtime
2. Construct correct URLs for the API service
3. Bake the API URL into the frontend build

## Troubleshooting

### CORS Errors
If you see CORS errors, ensure:
1. Post-configuration script has been run
2. GCS bucket CORS includes the frontend URL
3. API service has `allow_public_access = true`

### Signed URL Errors
If signed URL generation fails:
1. Verify service account has `serviceAccountTokenCreator` role
2. Check `GOOGLE_SERVICE_ACCOUNT_EMAIL` environment variable is set
3. Ensure service account email matches the running service

### Service Not Found
If services aren't accessible:
1. Check they were built and pushed: `./scripts/build-and-push.sh`
2. Verify images exist in Artifact Registry
3. Check Cloud Run service logs for errors

### Useful Commands

```bash
# Check service status
gcloud run services list --region=asia-south1

# View service logs
gcloud run services logs read api-service --region=asia-south1 --limit=50

# Check bucket CORS configuration
gcloud storage buckets describe gs://alchemy-super-over-inputs --format="json(cors)"

# Manually trigger post-configuration
./scripts/configure-post-terraform.sh
```

## Architecture Decisions

### Why No Load Balancer?
- Removed load balancer complexity in favor of direct Cloud Run URLs
- Simpler architecture with fewer moving parts
- Lower costs (no load balancer charges)
- Easier to debug and maintain

### Why Post-Configuration Script?
- Cloud Run service URLs are only known after creation
- Terraform can't reference URLs during the same apply
- Post-script provides clean separation of concerns
- Idempotent and safe to run multiple times