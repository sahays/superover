#!/bin/bash

# Super Over Alchemy - Build and Push Script
# Builds and pushes all service container images to Artifact Registry

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - can be overridden with environment variables
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}

# Try to read region from terraform.tfvars, fallback to environment or default
if [[ -f "terraform/terraform.tfvars" ]]; then
    REGION=${REGION:-$(grep '^region' terraform/terraform.tfvars | cut -d'"' -f2 2>/dev/null || echo "us-central1")}
else
    REGION=${REGION:-us-central1}
fi

REPOSITORY=${REPOSITORY:-super-over-alchemy}

# Service definitions (service-name:directory-name)
SERVICES="video-processor:video_processor audio-extractor:audio_extractor scene-analyzer:scene_analyzer media-inspector:media_inspector"

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

check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed or not in PATH"
        exit 1
    fi

    if [[ -z "$PROJECT_ID" ]]; then
        log_error "PROJECT_ID not set. Run: gcloud config set project YOUR_PROJECT_ID"
        exit 1
    fi

    # Check if Cloud Build API is enabled
    if ! gcloud services list --enabled --filter="name:cloudbuild.googleapis.com" --format="value(name)" | grep -q cloudbuild; then
        log_warn "Cloud Build API not enabled. Enabling now..."
        gcloud services enable cloudbuild.googleapis.com
    fi

    log_success "Prerequisites checked"
}

configure_docker() {
    log_info "Configuring Docker for Artifact Registry..."

    if gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet; then
        log_success "Docker configured for Artifact Registry"
    else
        log_error "Failed to configure Docker for Artifact Registry"
        exit 1
    fi
}

build_and_push_service() {
    local service_name=$1
    local service_dir=$2
    local image_tag="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${service_name}:latest"

    log_info "Building ${service_name} with Cloud Build..."

    # Check if service directory exists
    if [[ ! -d "$service_dir" ]]; then
        log_error "Service directory not found: $service_dir"
        return 1
    fi

    # Create service-specific Dockerfile if it doesn't exist
    local dockerfile_path="${service_dir}/Dockerfile"
    if [[ ! -f "$dockerfile_path" ]]; then
        log_info "Creating Dockerfile for ${service_name}..."
        create_service_dockerfile "$service_dir" "$service_name"
    fi

    # Build using Cloud Build
    if gcloud builds submit --tag "$image_tag" "$service_dir/"; then
        log_success "Built and pushed ${service_name}"
    else
        log_error "Failed to build ${service_name}"
        return 1
    fi
}

create_service_dockerfile() {
    local service_dir=$1
    local service_name=$2
    local dockerfile_path="${service_dir}/Dockerfile"

    cat > "$dockerfile_path" << EOF
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by ffmpeg and other libraries
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ffmpeg \\
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Set the Python path to include the current directory
ENV PYTHONPATH=/app

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Command to run the specific service
CMD ["uvicorn", "${service_dir}.main:app", "--host", "0.0.0.0", "--port", "8080"]
EOF

    log_success "Created Dockerfile for ${service_name}"
}

update_cloud_run_service() {
    local service_name=$1
    local image_tag="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${service_name}:latest"

    log_info "Updating Cloud Run service: ${service_name}-service..."

    if gcloud run deploy "${service_name}-service" \
        --image="$image_tag" \
        --region="$REGION" \
        --platform=managed \
        --quiet; then
        log_success "Updated ${service_name}-service"
    else
        log_warn "Failed to update ${service_name}-service (may not exist yet)"
    fi
}

# Parse command line arguments
SKIP_DEPLOY=false
BUILD_ONLY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-deploy)
            SKIP_DEPLOY=true
            shift
            ;;
        --service)
            BUILD_ONLY="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --skip-deploy         Skip Cloud Run service updates"
            echo "  --service SERVICE     Build only specific service"
            echo "  --help               Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  PROJECT_ID           GCP project ID"
            echo "  REGION              GCP region (default: us-central1)"
            echo "  REPOSITORY          Artifact Registry repository (default: super-over-alchemy)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo "==========================================="
    echo "Super Over Alchemy - Cloud Build & Push"
    echo "==========================================="
    echo "Project ID: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Repository: $REPOSITORY"
    echo "==========================================="

    check_prerequisites

    # Build specific service or all services
    if [[ -n "$BUILD_ONLY" ]]; then
        service_found=false
        for service_entry in $SERVICES; do
            service_name="${service_entry%:*}"
            service_dir="${service_entry#*:}"

            if [[ "$service_name" == "$BUILD_ONLY" ]]; then
                service_found=true
                build_and_push_service "$service_name" "$service_dir"
                if [[ "$SKIP_DEPLOY" != true ]]; then
                    update_cloud_run_service "$service_name"
                fi
                break
            fi
        done

        if [[ "$service_found" != true ]]; then
            log_error "Unknown service: $BUILD_ONLY"
            available_services=$(echo "$SERVICES" | tr ' ' '\n' | cut -d: -f1 | tr '\n' ' ')
            log_info "Available services: $available_services"
            exit 1
        fi
    else
        # Build all services
        for service_entry in $SERVICES; do
            service_name="${service_entry%:*}"
            service_dir="${service_entry#*:}"

            build_and_push_service "$service_name" "$service_dir"

            if [[ "$SKIP_DEPLOY" != true ]]; then
                update_cloud_run_service "$service_name"
            fi
        done
    fi

    echo "==================================="
    log_success "All operations completed successfully!"
    echo "==================================="
}

# Run main function
main "$@"