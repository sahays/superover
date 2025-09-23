#!/bin/bash

# Super Over Alchemy - Terraform State Import Script
# Imports existing GCP resources into the Terraform state to resolve "already exists" errors.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration - can be overridden with environment variables
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}

# Try to read region from terraform.tfvars, fallback to environment or default
if [[ -f "terraform/terraform.tfvars" ]]; then
    REGION=${REGION:-$(grep '^region' terraform/terraform.tfvars | cut -d'"' -f2 2>/dev/null || echo "us-central1")}
else
    REGION=${REGION:-us-central1}
fi

REPOSITORY=${REPOSITORY:-super-over-alchemy}
RAW_BUCKET=${RAW_BUCKET:-alchemy-super-over-inputs}
PROCESSED_BUCKET=${PROCESSED_BUCKET:-alchemy-super-over-outputs}

# --- Main Import Logic ---
main() {
    echo "=============================================="
    echo "Super Over Alchemy - Terraform State Import"
    echo "=============================================="
    echo "Project ID: $PROJECT_ID"
    echo "Region:     $REGION"
    echo "=============================================="

    log_info "Changing to the 'terraform' directory..."
    cd terraform

    log_info "Initializing Terraform..."
    terraform init

    log_info "Starting import process. This may take a few minutes..."

    # Import core resources
    terraform import google_artifact_registry_repository.repository "projects/$PROJECT_ID/locations/$REGION/repositories/$REPOSITORY"
    terraform import google_pubsub_topic.video_processor_jobs video-processor-jobs
    terraform import google_pubsub_topic.audio_extractor_jobs audio-extractor-jobs
    terraform import google_pubsub_topic.scene_analyzer_jobs scene-analyzer-jobs
    terraform import google_pubsub_topic.media_inspector_jobs media-inspector-jobs
    terraform import 'google_firestore_database.database' '(default)'

    # Import service accounts (from module)
    terraform import module.service_accounts.google_service_account.pubsub_invoker "projects/$PROJECT_ID/serviceAccounts/pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com"
    terraform import module.service_accounts.google_service_account.services "projects/$PROJECT_ID/serviceAccounts/super-over-services@$PROJECT_ID.iam.gserviceaccount.com"

    # Import storage buckets (from module)
    terraform import module.storage.google_storage_bucket.raw_videos "$RAW_BUCKET"
    terraform import module.storage.google_storage_bucket.processed_outputs "$PROCESSED_BUCKET"

    echo "=============================================="
    log_success "State import completed successfully!"
    log_info "Your Terraform state file should now be synchronized with your GCP resources."
    log_info "You can now re-run the deployment script: ./scripts/deploy.sh"
    echo "=============================================="
}

# Run main function
main "$@"
