#!/bin/bash

# --- Load Environment Variables ---
set -a
source ../.env
set +a

# --- Configuration (from .env) ---
# GCP_PROJECT_ID
# GCP_REGION
# GEMINI_MODEL
# GEMINI_API_KEY

# --- Service-Specific Configuration ---
SERVICE_NAME="scene-analyzer-service"
TIMEOUT="3600"
MAX_INSTANCES="5" # Keep low to protect API quotas

# --- Script Logic ---
echo "Starting deployment of '$SERVICE_NAME' to project '$GCP_PROJECT_ID' ભાષા..."
gcloud config set project $GCP_PROJECT_ID

gcloud run deploy $SERVICE_NAME \
  --source=.. \
  --region=$GCP_REGION \
  --timeout=$TIMEOUT \
  --concurrency=1 \
  --max-instances=$MAX_INSTANCES \
  --no-allow-unauthenticated \
  --set-env-vars="GEMINI_MODEL=${GEMINI_MODEL}" \
  --set-env-vars="GEMINI_API_KEY=${GEMINI_API_KEY}"

if [ $? -eq 0 ]; then
  echo "Deployment of '$SERVICE_NAME' completed successfully."
else
  echo "Error: Deployment of '$SERVICE_NAME' failed." >&2
  exit 1
fi