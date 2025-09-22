#!/bin/bash

# --- Load Environment Variables ---
set -a
source ../.env
set +a

# --- Configuration (from .env) ---
# GCP_PROJECT_ID
# GCP_REGION
# WORKFLOW_NAME

# --- Service-Specific Configuration ---
SERVICE_NAME="job-creator-service"

# --- Script Logic ---
echo "Starting deployment of '$SERVICE_NAME' to project '$GCP_PROJECT_ID'ப்பான"
gcloud config set project $GCP_PROJECT_ID

echo "Deploying from directory: ../job_creator"
gcloud functions deploy $SERVICE_NAME \
  --gen2 \
  --runtime=python39 \
  --region=$GCP_REGION \
  --source=../job_creator \
  --entry-point=create_job \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars="WORKFLOW_NAME=$WORKFLOW_NAME" \
  --set-env-vars="GCP_LOCATION=$GCP_REGION"

if [ $? -eq 0 ]; then
  echo "Deployment of '$SERVICE_NAME' completed successfully."
  gcloud functions describe $SERVICE_NAME --region=$GCP_REGION --format="value(url)"
else
  echo "Error: Deployment of '$SERVICE_NAME' failed." >&2
  exit 1
fi