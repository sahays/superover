#!/bin/bash

# Deploy services to Cloud Run (gen2).
# Builds Docker images locally, pushes to GCR, deploys to Cloud Run.
#
# Services:
#   api    — FastAPI + Vite SPA (same-origin, no CORS)
#   worker — Unified worker (Transcoder API + Gemini, no FFmpeg)
#
# Usage:
#   ./deploy.sh                          # Deploy all services
#   ./deploy.sh api                      # Deploy API only
#   ./deploy.sh worker                   # Deploy worker only
#   ./deploy.sh api worker               # Deploy specific services
#
# Flags:
#   --skip-checks    Skip pre-deploy lint/format/build checks
#   --skip-push      Build images locally but don't push or deploy (for testing)
#
# Examples:
#   ./deploy.sh --skip-checks worker     # Redeploy worker after a mid-deploy failure
#   ./deploy.sh --skip-push              # Validate all Docker builds without deploying

set -e

# ── Parse arguments ──────────────────────────────────────
SERVICES=()
SKIP_CHECKS=false
SKIP_PUSH=false

for arg in "$@"; do
    case $arg in
        --skip-checks) SKIP_CHECKS=true ;;
        --skip-push)   SKIP_PUSH=true ;;
        api|worker|all)
            SERVICES+=("$arg") ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: ./deploy.sh [api|worker|all] [--skip-checks] [--skip-push]"
            exit 1 ;;
    esac
done

# Default to "all" if no services specified
if [ ${#SERVICES[@]} -eq 0 ]; then
    SERVICES=("all")
fi

# Expand "all" into individual flags
DEPLOY_API=false
DEPLOY_WORKER=false

for svc in "${SERVICES[@]}"; do
    case $svc in
        all)    DEPLOY_API=true; DEPLOY_WORKER=true ;;
        api)    DEPLOY_API=true ;;
        worker) DEPLOY_WORKER=true ;;
    esac
done

# ── Load environment variables ───────────────────────────
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

PROJECT_ID=${GCP_PROJECT_ID:?GCP_PROJECT_ID must be set}
REGION=${GCP_REGION:-asia-south1}
SN=${SERVICE_NAME:-superover}
REGISTRY="gcr.io/$PROJECT_ID"

# Shared env vars for backend services (API + worker).
#
# IMPORTANT lessons learned:
#   - PORT is RESERVED by Cloud Run. Never pass it here. Use --port flag instead.
#   - Gemini SDK uses ADC (Application Default Credentials) — no API key needed.
#   - Gemini model vars are needed by worker for scene analysis and image generation.
BACKEND_ENVS="GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=$REGION,\
ENVIRONMENT=production,\
UPLOADS_BUCKET=$UPLOADS_BUCKET,\
PROCESSED_BUCKET=$PROCESSED_BUCKET,\
RESULTS_BUCKET=$RESULTS_BUCKET,\
FIRESTORE_DATABASE=${FIRESTORE_DATABASE:-(default)},\
SERVICE_NAME=$SN,\
SCENE_PROCESSING_MODE=${SCENE_PROCESSING_MODE:-sequential},\
MAX_GEMINI_WORKERS=${MAX_GEMINI_WORKERS:-10},\
GEMINI_REGION=${GEMINI_REGION:-global},\
GEMINI_DEFAULT_MODEL=${GEMINI_DEFAULT_MODEL:-gemini-3-pro-preview},\
GEMINI_DEFAULT_OUTPUT_TOKENS=${GEMINI_DEFAULT_OUTPUT_TOKENS:-65536},\
GEMINI_IMAGE_MODEL=${GEMINI_IMAGE_MODEL:-gemini-3-pro-image-preview},\
GEMINI_IMAGE_OUTPUT_TOKENS=${GEMINI_IMAGE_OUTPUT_TOKENS:-32768},\
TRANSCODER_LOCATION=${TRANSCODER_LOCATION:-asia-south1}"


# ── Helpers ──────────────────────────────────────────────
DEPLOY_START=$(date +%s)

step_start() {
    echo ""
    echo ">> $1"
    STEP_START=$(date +%s)
}

step_done() {
    local elapsed=$(( $(date +%s) - STEP_START ))
    echo "   Done (${elapsed}s)"
}

build_and_deploy() {
    # Usage: build_and_deploy <dockerfile> <image-tag> <build-context> <service-name> <extra-gcloud-flags...>
    local dockerfile="$1"
    local image_tag="$2"
    local build_context="$3"
    local service_name="$4"
    shift 4
    local extra_flags=("$@")

    step_start "Building $service_name image..."
    docker build -f "$dockerfile" -t "$REGISTRY/$image_tag" "$build_context"
    step_done

    if [ "$SKIP_PUSH" = false ]; then
        step_start "Pushing $service_name image..."
        docker push "$REGISTRY/$image_tag"
        step_done

        step_start "Deploying $service_name..."
        gcloud run deploy "$service_name" \
            --image "$REGISTRY/$image_tag" \
            --platform managed \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --execution-environment gen2 \
            --quiet \
            "${extra_flags[@]}"
        step_done
    fi
}

# ── 0. Pre-deploy checks ────────────────────────────────
if [ "$SKIP_CHECKS" = false ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    "$SCRIPT_DIR/pre-deploy.sh"
else
    echo ">> Skipping pre-deploy checks (--skip-checks)"
fi

# Ensure docker can push to GCR
gcloud auth configure-docker --quiet 2>/dev/null

SELECTED="$(
    [ "$DEPLOY_API" = true ] && echo -n "api " || true
    [ "$DEPLOY_WORKER" = true ] && echo -n "worker " || true
)"

echo ""
echo "========================================"
echo "Deploying to Cloud Run (gen2)"
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Prefix:   $SN"
echo "Services: $SELECTED"
echo "========================================"

# ── 1. API (serves both REST API and Vite SPA) ──────────
if [ "$DEPLOY_API" = true ]; then
    build_and_deploy \
        Dockerfile.api "$SN-frontend" . "$SN-frontend" \
        --allow-unauthenticated \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 300
fi

# ── 2. Unified Worker ───────────────────────────────────
# Worker flags:
#   --no-allow-unauthenticated  (internal only, no public access)
#   --no-cpu-throttling         (CRITICAL: without this, Cloud Run throttles CPU
#                                outside of request handling, which kills poll loops)
#   --min-instances 1           (keeps worker alive for continuous Firestore polling)
if [ "$DEPLOY_WORKER" = true ]; then
    build_and_deploy \
        Dockerfile.worker "$SN-worker" . "$SN-worker" \
        --no-allow-unauthenticated \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 3600 \
        --min-instances 1 \
        --max-instances 1 \
        --concurrency 1 \
        --no-cpu-throttling
fi

# ── Summary ──────────────────────────────────────────────
TOTAL_ELAPSED=$(( $(date +%s) - DEPLOY_START ))

API_URL=${API_URL:-$(gcloud run services describe "$SN-frontend" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null || echo "(not deployed)")}

echo ""
echo "========================================"
echo "Deployment complete! (${TOTAL_ELAPSED}s total)"
echo "========================================"
echo "App (API + SPA): $API_URL"
echo "API Docs:        $API_URL/docs"
echo "Worker:          $SN-worker (internal)"
echo "========================================"
