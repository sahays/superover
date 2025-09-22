#!/bin/bash

# --- Load Environment Variables ---
set -a
source ../.env
set +a

# --- Configuration (from .env) ---
# GCP_PROJECT_ID
# GCP_REGION
# CHUNK_DURATION
# COMPRESS_RESOLUTION
# COMPRESS_FIRST

# --- Service-Specific Configuration ---
SERVICE_NAME="video-processor-service"
TIMEOUT="3600"
MAX_INSTANCES="10"

# --- Script Logic ---
echo "Starting deployment of '$SERVICE_NAME' to project '$GCP_PROJECT_ID'..."
gcloud config set project $GCP_PROJECT_ID

gcloud run deploy $SERVICE_NAME \
  --source=.. \
  --region=$GCP_REGION \
  --timeout=$TIMEOUT \
  --concurrency=1 \
  --max-instances=$MAX_INSTANCES \
  --no-allow-unauthenticated \
  --set-env-vars="CHUNK_DURATION=${CHUNK_DURATION}" \
  --set-env-vars="COMPRESS_RESOLUTION=${COMPRESS_RESOLUTION}" \
  --set-env-vars="COMPRESS_FIRST=${COMPRESS_FIRST}"

if [ $? -eq 0 ]; then
  echo "Deployment of '$SERVICE_NAME' completed successfully."
else
  echo "Error: Deployment of '$SERVICE_NAME' failed." >&2
  exit 1
fi