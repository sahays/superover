#!/bin/bash

# Super Over Alchemy - Post-Terraform Configuration Script
# Updates GCS bucket CORS with specific Cloud Run service URLs after deployment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - read from .env file
if [[ -f ".env" ]]; then
    # Source .env file to load variables
    export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID=${PROJECT_ID:-${GCP_PROJECT_ID:-$(gcloud config get-value project)}}
REGION=${REGION:-${GCP_REGION:-asia-south1}}
RAW_UPLOADS_BUCKET_NAME=${RAW_UPLOADS_BUCKET_NAME:-alchemy-super-over-inputs}

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Main execution
main() {
    echo "========================================================"
    echo "Super Over Alchemy - Post-Terraform Configuration"
    echo "========================================================"
    echo "Project ID: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Bucket: $RAW_UPLOADS_BUCKET_NAME"
    echo "========================================================"

    # Get frontend service URL
    log_info "Fetching frontend-service URL..."
    FRONTEND_URL=$(gcloud run services describe frontend-service \
        --region="$REGION" \
        --format="value(status.url)" 2>/dev/null || echo "")

    if [[ -z "$FRONTEND_URL" ]]; then
        log_error "Could not fetch frontend-service URL. Ensure the service is deployed."
        exit 1
    fi

    log_success "Frontend URL: $FRONTEND_URL"

    # Create CORS configuration file
    log_info "Creating CORS configuration..."
    cat > /tmp/cors-config.json << EOF
[
  {
    "origin": ["$FRONTEND_URL", "http://localhost:3000", "http://localhost:3001"],
    "method": ["GET", "HEAD", "PUT", "POST", "DELETE"],
    "responseHeader": ["Content-Type", "Content-Length", "Content-MD5", "x-goog-resumable"],
    "maxAgeSeconds": 3600
  }
]
EOF

    log_info "CORS configuration:"
    cat /tmp/cors-config.json

    # Apply CORS configuration to bucket
    log_info "Applying CORS configuration to gs://$RAW_UPLOADS_BUCKET_NAME..."
    if gcloud storage buckets update "gs://$RAW_UPLOADS_BUCKET_NAME" --cors-file=/tmp/cors-config.json; then
        log_success "CORS configuration applied successfully!"
    else
        log_error "Failed to apply CORS configuration"
        exit 1
    fi

    # Cleanup
    rm -f /tmp/cors-config.json

    echo "========================================================"
    log_success "Post-Terraform configuration completed!"
    echo "========================================================"
    echo ""
    log_info "Summary of configured resources:"
    echo "  - Bucket: gs://$RAW_UPLOADS_BUCKET_NAME"
    echo "  - Allowed origins: $FRONTEND_URL, http://localhost:3000, http://localhost:3001"
    echo "  - Allowed methods: GET, HEAD, PUT, POST, DELETE"
    echo ""
    log_success "Your application is ready to use!"
}

# Run main function
main "$@"
