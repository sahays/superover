#!/bin/bash

# --- Load Environment Variables ---
set -a
source ../.env
set +a

# --- Configuration (from .env) ---
# GCP_PROJECT_ID
# GCP_REGION

# --- Service-Specific Configuration ---
SERVICE_NAME="workflow-manager-service"

# --- Script Logic ---
echo "Starting deployment of '$SERVICE_NAME' to project '$GCP_PROJECT_ID'வுகளை..."
gcloud config set project $GCP_PROJECT_ID

echo "Deploying from directory: ../workflow_manager"
gcloud functions deploy $SERVICE_NAME \
  --gen2 \
  --runtime=python39 \
  --region=$GCP_REGION \
  --source=../workflow_manager \
  --entry-point=manage_workflow \
  --trigger-http \
  --allow-unauthenticated

if [ $? -eq 0 ]; then
  echo "Deployment of '$SERVICE_NAME' completed successfully."
  gcloud functions describe $SERVICE_NAME --region=$GCP_REGION --format="value(url)"
else
  echo "Error: Deployment of '$SERVICE_NAME' failed." >&2
  exit 1
fi