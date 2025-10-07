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

# Configuration - read from .env file
if [[ -f ".env" ]]; then
    # Source .env file to load variables
    export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID=${PROJECT_ID:-${GCP_PROJECT_ID:-$(gcloud config get-value project)}}
REGION=${REGION:-${GCP_REGION:-us-central1}}
REPOSITORY=${REPOSITORY:-super-over-alchemy}
RAW_BUCKET=${RAW_BUCKET:-${RAW_UPLOADS_BUCKET_NAME:-alchemy-super-over-inputs}}
PROCESSED_BUCKET=${PROCESSED_BUCKET:-${PROCESSED_OUTPUTS_BUCKET_NAME:-alchemy-super-over-outputs}}

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

    # Function to safely import (ignore errors if resource already in state)
    safe_import() {
        local resource=$1
        local id=$2
        log_info "Importing $resource..."
        if terraform import "$resource" "$id" 2>&1 | grep -q "Resource already managed"; then
            log_info "  Already in state, skipping."
        fi
    }

    # Import core resources
    safe_import "google_artifact_registry_repository.repository" "projects/$PROJECT_ID/locations/$REGION/repositories/$REPOSITORY"
    safe_import "google_compute_global_address.frontend_ip" "projects/$PROJECT_ID/global/addresses/frontend-lb-ip"
    safe_import "google_compute_managed_ssl_certificate.frontend_ssl" "projects/$PROJECT_ID/global/sslCertificates/frontend-ssl-cert"
    safe_import "google_pubsub_topic.scene_analysis_jobs" "projects/$PROJECT_ID/topics/scene-analysis-jobs"
    safe_import "google_firestore_database.database" "projects/$PROJECT_ID/databases/(default)"

    # Import service accounts (from module)
    safe_import "module.service_accounts.google_service_account.pubsub_invoker" "projects/$PROJECT_ID/serviceAccounts/pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com"
    safe_import "module.service_accounts.google_service_account.services" "projects/$PROJECT_ID/serviceAccounts/super-over-services@$PROJECT_ID.iam.gserviceaccount.com"

    # Import storage buckets (from module)
    safe_import "module.storage.google_storage_bucket.raw_videos" "$RAW_BUCKET"
    safe_import "module.storage.google_storage_bucket.processed_outputs" "$PROCESSED_BUCKET"

    # Import Cloud Run services
    safe_import "module.frontend_service.google_cloud_run_service.service" "locations/$REGION/namespaces/$PROJECT_ID/services/frontend-service"
    safe_import "module.api_service.google_cloud_run_service.service" "locations/$REGION/namespaces/$PROJECT_ID/services/api-service"

    # Import Cloud Run job
    safe_import "module.scene_analyzer_worker.google_cloud_run_v2_job.job" "projects/$PROJECT_ID/locations/$REGION/jobs/scene-analyzer-worker"

    echo "=============================================="
    log_success "State import completed successfully!"
    log_info "Your Terraform state file should now be synchronized with your GCP resources."
    log_info "You can now re-run the deployment script: ./scripts/deploy.sh"
    echo "=============================================="
}

# Run main function
main "$@"
