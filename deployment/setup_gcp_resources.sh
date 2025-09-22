#!/bin/bash

# This script sources variables from the .env file in the parent directory
# to provision the necessary GCP infrastructure for the project.

# --- Load Environment Variables ---
set -a # automatically export all variables
source ../.env
set +a

# --- Configuration (from .env) ---
# GCP_PROJECT_ID
# GCP_REGION
# RAW_UPLOADS_BUCKET_NAME
# PROCESSED_OUTPUTS_BUCKET_NAME
# INVOKER_SERVICE_ACCOUNT_NAME

# --- Script Logic ---
echo "Starting setup of GCP resources for project '$GCP_PROJECT_ID'வுகளை..."

# --- 0. Set Project ---
gcloud config set project $GCP_PROJECT_ID

# --- 1. Enable APIs ---
echo "Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  workflows.googleapis.com \
  workflowexecutions.googleapis.com \
  cloudfunctions.googleapis.com \
  iam.googleapis.com

# --- 2. Create GCS Buckets ---
echo "Creating GCS buckets..."
gsutil mb -b on -l $GCP_REGION gs://$RAW_UPLOADS_BUCKET_NAME
gsutil mb -b on -l $GCP_REGION gs://$PROCESSED_OUTPUTS_BUCKET_NAME

# --- 3. Create Firestore Database ---
echo "Creating Firestore database in Native mode..."
gcloud firestore databases create --location=$GCP_REGION --type=firestore-native

# --- 4. Create Pub/Sub Topics ---
echo "Creating Pub/Sub topics..."
gcloud pubsub topics create raw-video-uploads
gcloud pubsub topics create video-processing-complete

# --- 5. Create Service Account for Pub/Sub Invoker ---
echo "Creating invoker service account..."
gcloud iam service-accounts create $INVOKER_SERVICE_ACCOUNT_NAME \
  --display-name="Pub/Sub to Cloud Run Invoker"

# --- 6. Grant IAM Permissions ---
GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')
PUBSUB_SERVICE_AGENT="service-${GCP_PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:${PUBSUB_SERVICE_AGENT}" \
    --role="roles/iam.serviceAccountTokenCreator"

echo "------------------------------------------"
echo "GCP resource setup completed successfully."
echo "------------------------------------------"