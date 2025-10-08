#!/bin/bash

# Deploy script for Cloud Run
set -e

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID=${GCP_PROJECT_ID}
REGION=${GCP_REGION:-asia-south1}

echo "================================"
echo "Deploying to Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "================================"

# Build and push API service
echo "Building API service..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/api-service -f Dockerfile.api .

echo "Deploying API service..."
gcloud run deploy api-service \
    --image gcr.io/$PROJECT_ID/api-service \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION,ENVIRONMENT=production,UPLOADS_BUCKET=$UPLOADS_BUCKET,PROCESSED_BUCKET=$PROCESSED_BUCKET,RESULTS_BUCKET=$RESULTS_BUCKET,GEMINI_API_KEY=$GEMINI_API_KEY" \
    --memory 2Gi \
    --timeout 300

# Build and push Worker service
echo "Building Worker service..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/video-worker -f Dockerfile.worker .

echo "Deploying Worker service..."
gcloud run deploy video-worker \
    --image gcr.io/$PROJECT_ID/video-worker \
    --platform managed \
    --region $REGION \
    --no-allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION,ENVIRONMENT=production,UPLOADS_BUCKET=$UPLOADS_BUCKET,PROCESSED_BUCKET=$PROCESSED_BUCKET,RESULTS_BUCKET=$RESULTS_BUCKET,GEMINI_API_KEY=$GEMINI_API_KEY" \
    --memory 4Gi \
    --timeout 3600 \
    --min-instances 1

echo "================================"
echo "Deployment complete!"
echo "================================"

# Get API service URL
API_URL=$(gcloud run services describe api-service --region $REGION --format='value(status.url)')
echo "API URL: $API_URL"
echo "Docs: $API_URL/docs"
