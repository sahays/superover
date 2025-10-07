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

# Configuration - read from .env file
if [[ -f ".env" ]]; then
    # Source .env file to load variables
    export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID=${PROJECT_ID:-${GCP_PROJECT_ID:-$(gcloud config get-value project)}}
REGION=${REGION:-${GCP_REGION:-us-central1}}

REPOSITORY=${REPOSITORY:-super-over-alchemy}

# Service definitions (service-name:directory-name)
SERVICES="frontend-service:frontend api-service:services/api_service scene-analyzer-worker:services/scene_analyzer_worker"

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

    # Get project number for Cloud Run URLs
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
    if [[ -z "$PROJECT_NUMBER" ]]; then
        log_error "Could not get project number for $PROJECT_ID"
        exit 1
    fi
    log_info "Project number: $PROJECT_NUMBER"

    # Check if Cloud Build API is enabled
    if ! gcloud services list --enabled --filter="name:cloudbuild.googleapis.com" --format="value(name)" | grep -q cloudbuild; then
        log_warn "Cloud Build API not enabled. Enabling now..."
        gcloud services enable cloudbuild.googleapis.com
    fi

    log_success "Prerequisites checked"
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

    local dockerfile_path="${service_dir}/Dockerfile"
    local root_dockerfile="./Dockerfile"

    # Always recreate the Dockerfile to ensure it is correct
    log_info "Creating Dockerfile for ${service_name} at ${dockerfile_path}..."
    create_service_dockerfile "$service_dir" "$service_name"

    log_info "Copying Dockerfile to project root for build..."
    cp "$dockerfile_path" "$root_dockerfile"

    # Use a trap to ensure the temporary Dockerfile is always removed
    trap 'rm -f "$root_dockerfile"' RETURN

    # Build using Cloud Build from the project root as context
    log_info "Using project root as build context..."
    log_info "Building with region: $REGION"

    if gcloud builds submit --tag "$image_tag" . --region="$REGION"; then
        log_success "Built and pushed ${service_name}"
    else
        log_warn "Regional build failed, trying global region..."
        # Fallback to global region if regional fails
        if gcloud builds submit --tag "$image_tag" . --region=global; then
            log_success "Built and pushed ${service_name}"
        else
            log_error "Failed to build ${service_name}"
            return 1
        fi
    fi
}

create_service_dockerfile() {
    local service_dir=$1
    local service_name=$2
    local dockerfile_path="${service_dir}/Dockerfile"

    if [[ "$service_name" == "frontend-service" ]]; then
        # Construct API URL using project number (not project ID)
        local api_url="https://api-service-${PROJECT_NUMBER}.${REGION}.run.app"
        log_info "Baking API URL into frontend build: $api_url"

        # Create Next.js Dockerfile
        cat > "$dockerfile_path" << EOF
# Use Node.js 18 Alpine image
FROM node:18-alpine AS base

# Install dependencies only when needed
FROM base AS deps
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies based on the preferred package manager
COPY $service_dir/package.json $service_dir/package-lock.json* ./
RUN npm ci

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY $service_dir/ .

# Set API URL for Next.js build
ENV NEXT_PUBLIC_API_URL=$api_url

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
# Uncomment the following line in case you want to disable telemetry during the build.
ENV NEXT_TELEMETRY_DISABLED 1

RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
# Uncomment the following line in case you want to disable telemetry during runtime.
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
# set hostname to localhost
ENV HOSTNAME "0.0.0.0"

# server.js is created by next build from the standalone output
# https://nextjs.org/docs/pages/api-reference/next-config-js/output
CMD ["node", "server.js"]
EOF
    else
        # Create Python service Dockerfile
        # Convert directory path to Python module path (replace / with .)
        local python_module_path=$(echo "$service_dir" | tr '/' '.')

        # Determine if this is a worker or API service
        local cmd_line
        if [[ "$service_name" == *"worker"* ]]; then
            # Worker service - runs as standalone Python script
            cmd_line='CMD ["python", "-u", "'"$service_dir"'/main.py"]'
        else
            # API service - runs with uvicorn
            cmd_line='CMD ["uvicorn", "'"$python_module_path"'.main:app", "--host", "0.0.0.0", "--port", "8080"]'
        fi

        cat > "$dockerfile_path" << EOF
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by ffmpeg and other libraries
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the common library code
COPY common/ ./common/

# Install the media_utils package if it exists
RUN if [ -d "./common/media_utils" ]; then pip install --no-cache-dir ./common/media_utils; fi

# Copy the specific service code
COPY $service_dir/ ./$service_dir/

# Copy and install service-specific requirements
COPY $service_dir/requirements.txt ./service_requirements.txt
RUN pip install --no-cache-dir -r service_requirements.txt

# Set the Python path to include the current directory
ENV PYTHONPATH=/app

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Command to run the specific service
$cmd_line
EOF
    fi

    log_success "Created Dockerfile for ${service_name}"
}

update_cloud_run_service() {
    local service_name=$1
    local image_tag="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${service_name}:latest"

    # Check if this is a worker (job) or a service
    if [[ "$service_name" == *"worker"* ]]; then
        log_info "Updating Cloud Run job: ${service_name}..."

        if gcloud run jobs update "${service_name}" \
            --image="$image_tag" \
            --region="$REGION" \
            --quiet 2>/dev/null; then
            log_success "Updated ${service_name} job"
        else
            log_warn "Failed to update ${service_name} job (may not exist yet - will be created by Terraform)"
        fi
    else
        log_info "Updating Cloud Run service: ${service_name}..."

        if gcloud run services update "${service_name}" \
            --image="$image_tag" \
            --region="$REGION" \
            --platform=managed \
            --quiet 2>/dev/null; then
            log_success "Updated ${service_name} service"
        else
            log_warn "Failed to update ${service_name} service (may not exist yet - will be created by Terraform)"
        fi
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
            echo "  PROJECT_ID           GCP project ID (or set GCP_PROJECT_ID in .env)"
            echo "  REGION              GCP region (or set GCP_REGION in .env, default: us-central1)"
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