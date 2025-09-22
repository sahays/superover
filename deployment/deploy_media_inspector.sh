#!/bin/bash

# --- Load Environment Variables ---
set -a
source ../.env
set +a

# --- Configuration (from .env) ---
# GCP_PROJECT_ID
# GCP_REGION

# --- Service-Specific Configuration ---
SERVICE_NAME="media-inspector-service"
TIMEOUT="600"
MAX_INSTANCES="10"

# --- Script Logic ---
echo "Starting deployment of '$SERVICE_NAME' to project '$GCP_PROJECT_ID' ભા..."
gcloud config set project $GCP_PROJECT_ID

gcloud run deploy $SERVICE_NAME \
  --source=.. \
  --region=$GCP_REGION \
  --timeout=$TIMEOUT \
  --concurrency=1 \
  --max-instances=$MAX_INSTANCES \
  --no-allow-unauthenticated

if [ $? -eq 0 ]; then
  echo "Deployment of '$SERVICE_NAME' completed successfully."
else
  echo "Error: Deployment of '$SERVICE_NAME' failed." >&2
  exit 1
fi