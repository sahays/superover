#!/bin/bash

# Super Over Alchemy - Complete Deployment Script
# Deploys infrastructure and builds/pushes all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
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

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed"
        exit 1
    fi

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if [[ ! -f "terraform/terraform.tfvars" ]]; then
        log_error "terraform/terraform.tfvars not found. Copy from terraform.tfvars.example and configure."
        exit 1
    fi

    log_success "Prerequisites checked"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying infrastructure with Terraform..."

    cd terraform

    if ! terraform init; then
        log_error "Terraform init failed"
        exit 1
    fi

    if ! terraform validate; then
        log_error "Terraform validation failed"
        exit 1
    fi

    # Deploy foundation infrastructure first (without Cloud Run services)
    log_info "Deploying foundation infrastructure..."
    terraform apply -auto-approve \
        -target=google_project_service.required_apis \
        -target=google_artifact_registry_repository.repository \
        -target=module.service_accounts \
        -target=google_pubsub_topic.video_processor_jobs \
        -target=google_pubsub_topic.audio_extractor_jobs \
        -target=google_pubsub_topic.scene_analyzer_jobs \
        -target=google_pubsub_topic.media_inspector_jobs \
        -target=google_firestore_database.database \
        -target=module.storage \
        -target=google_project_iam_member.cloudbuild_logs_writer \
        -target=google_project_iam_member.cloudbuild_storage_admin \
        -target=google_project_iam_member.cloudbuild_artifact_writer \
        -target=google_project_iam_member.compute_sa_cloudbuild_editor \
        -target=google_project_iam_member.compute_sa_storage_admin

    cd ..
    log_success "Foundation infrastructure deployed"
}

# Deploy services after images are built
deploy_services() {
    log_info "Deploying Cloud Run services..."

    cd terraform

    log_info "Applying remaining terraform configuration..."

    # Target only the Pub/Sub subscription modules since Cloud Run services are already deployed
    log_info "Planning Pub/Sub subscriptions deployment..."
    terraform plan -target=module.video_processor_pubsub -target=module.audio_extractor_pubsub -target=module.scene_analyzer_pubsub -target=module.media_inspector_pubsub

    # Apply with auto-approve, targeting only the subscription modules
    if ! terraform apply -auto-approve -target=module.video_processor_pubsub -target=module.audio_extractor_pubsub -target=module.scene_analyzer_pubsub -target=module.media_inspector_pubsub; then
        log_error "Service deployment failed"
        exit 1
    fi

    cd ..
    log_success "Services deployed"
}

# Build and push containers
build_and_push() {
    log_info "Building and pushing container images..."

    if ! ./scripts/build-and-push.sh --skip-deploy; then
        log_error "Build and push failed"
        exit 1
    fi

    log_success "All services built and pushed"
}

# Main deployment
main() {
    echo "=============================================="
    echo "Super Over Alchemy - Complete Deployment"
    echo "=============================================="

    check_prerequisites
    deploy_infrastructure

    log_info "Waiting for 20 seconds for IAM permissions to propagate..."
    sleep 20

    build_and_push
    deploy_services

    echo "=============================================="
    log_success "Deployment completed successfully!"
    echo ""
    log_info "Next steps:"
    echo "1. Upload a video to your raw videos bucket to test the pipeline"
    echo "2. Monitor Cloud Run services in the GCP Console"
    echo "3. Check Cloud Logging for service logs"
    echo "=============================================="
}

main "$@"