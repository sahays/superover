#!/bin/bash

# Deploy services to Cloud Run (gen2).
# Builds Docker images locally, pushes to GCR, deploys to Cloud Run.
#
# Usage:
#   ./deploy.sh                          # Deploy all services
#   ./deploy.sh api                      # Deploy API only
#   ./deploy.sh frontend                 # Deploy frontend only
#   ./deploy.sh workers                  # Deploy both workers
#   ./deploy.sh media-worker             # Deploy media worker only
#   ./deploy.sh ai-worker                # Deploy AI worker only
#   ./deploy.sh api frontend             # Deploy specific services
#
# Flags:
#   --skip-checks    Skip pre-deploy lint/format/build checks
#   --skip-push      Build images locally but don't push or deploy (for testing)
#
# Examples:
#   ./deploy.sh --skip-checks frontend   # Redeploy frontend without re-linting
#   ./deploy.sh --skip-checks workers    # Redeploy workers after a mid-deploy failure
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
        api|frontend|media-worker|ai-worker|workers|all)
            SERVICES+=("$arg") ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: ./deploy.sh [api|frontend|workers|media-worker|ai-worker|all] [--skip-checks] [--skip-push]"
            exit 1 ;;
    esac
done

# Default to "all" if no services specified
if [ ${#SERVICES[@]} -eq 0 ]; then
    SERVICES=("all")
fi

# Expand "all" and "workers" into individual flags
DEPLOY_API=false
DEPLOY_FRONTEND=false
DEPLOY_MEDIA_WORKER=false
DEPLOY_AI_WORKER=false

for svc in "${SERVICES[@]}"; do
    case $svc in
        all)          DEPLOY_API=true; DEPLOY_FRONTEND=true; DEPLOY_MEDIA_WORKER=true; DEPLOY_AI_WORKER=true ;;
        api)          DEPLOY_API=true ;;
        frontend)     DEPLOY_FRONTEND=true ;;
        workers)      DEPLOY_MEDIA_WORKER=true; DEPLOY_AI_WORKER=true ;;
        media-worker) DEPLOY_MEDIA_WORKER=true ;;
        ai-worker)    DEPLOY_AI_WORKER=true ;;
    esac
done

# ── Load environment variables ───────────────────────────
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

PROJECT_ID=${GCP_PROJECT_ID:?GCP_PROJECT_ID must be set}
REGION=${GCP_REGION:-asia-south1}
SN=${SERVICE_NAME:-super-over}
REGISTRY="gcr.io/$PROJECT_ID"

# Shared env vars for backend services (API + workers).
#
# IMPORTANT lessons learned:
#   - PORT is RESERVED by Cloud Run. Never pass it here. Use --port flag instead.
#   - GEMINI_API_KEY empty = use Application Default Credentials (ADC).
#   - Gemini model vars are needed by AI worker for scene analysis and image generation.
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
GEMINI_DEFAULT_MODEL=${GEMINI_DEFAULT_MODEL},\
GEMINI_DEFAULT_OUTPUT_TOKENS=${GEMINI_DEFAULT_OUTPUT_TOKENS:-65536},\
GEMINI_IMAGE_MODEL=${GEMINI_IMAGE_MODEL},\
GEMINI_IMAGE_OUTPUT_TOKENS=${GEMINI_IMAGE_OUTPUT_TOKENS:-32768}"

# Only include GEMINI_API_KEY if set (empty = ADC, no need to pass it)
if [ -n "$GEMINI_API_KEY" ]; then
    BACKEND_ENVS="$BACKEND_ENVS,GEMINI_API_KEY=$GEMINI_API_KEY"
fi

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
    [ "$DEPLOY_FRONTEND" = true ] && echo -n "frontend " || true
    [ "$DEPLOY_MEDIA_WORKER" = true ] && echo -n "media-worker " || true
    [ "$DEPLOY_AI_WORKER" = true ] && echo -n "ai-worker " || true
)"

echo ""
echo "========================================"
echo "Deploying to Cloud Run (gen2)"
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Prefix:   $SN"
echo "Services: $SELECTED"
echo "========================================"

# ── 1. API ───────────────────────────────────────────────
if [ "$DEPLOY_API" = true ]; then
    build_and_deploy \
        Dockerfile.api "$SN-api" . "$SN-api" \
        --allow-unauthenticated \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 300
fi

# ── 2. Frontend ──────────────────────────────────────────
if [ "$DEPLOY_FRONTEND" = true ]; then
    # Frontend needs API_URL baked in at build time (NEXT_PUBLIC_* are inlined by Next.js).
    # Fetch it from the deployed API service even if API wasn't deployed this run.
    API_URL=$(gcloud run services describe "$SN-api" \
        --region "$REGION" --project "$PROJECT_ID" \
        --format='value(status.url)' 2>/dev/null || echo "")

    if [ -z "$API_URL" ]; then
        echo "ERROR: Cannot deploy frontend - API service ($SN-api) not found."
        echo "       Deploy the API first: ./deploy.sh api"
        exit 1
    fi
    echo "   Using API URL: $API_URL"

    step_start "Building frontend image (NEXT_PUBLIC_API_URL=$API_URL)..."
    docker build \
        -f frontend/Dockerfile \
        --build-arg NEXT_PUBLIC_API_URL="$API_URL" \
        -t "$REGISTRY/$SN-frontend" \
        frontend/
    step_done

    if [ "$SKIP_PUSH" = false ]; then
        step_start "Pushing frontend image..."
        docker push "$REGISTRY/$SN-frontend"
        step_done

        # IMPORTANT: Use --port 8080, NOT --set-env-vars "PORT=8080".
        # PORT is a reserved environment variable in Cloud Run.
        step_start "Deploying $SN-frontend..."
        gcloud run deploy "$SN-frontend" \
            --image "$REGISTRY/$SN-frontend" \
            --platform managed \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --execution-environment gen2 \
            --allow-unauthenticated \
            --port 8080 \
            --cpu 4 \
            --memory 8Gi \
            --timeout 60 \
            --quiet
        step_done

        FRONTEND_URL=$(gcloud run services describe "$SN-frontend" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format='value(status.url)')
        echo "   Frontend URL: $FRONTEND_URL"

        # Update API with FRONTEND_URL so CORS allows the frontend origin.
        step_start "Updating $SN-api with FRONTEND_URL for CORS..."
        gcloud run services update "$SN-api" \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --update-env-vars "FRONTEND_URL=$FRONTEND_URL" \
            --quiet
        step_done
    fi
fi

# ── 3. Media Worker ─────────────────────────────────────
# Workers use:
#   --no-allow-unauthenticated  (internal only, no public access)
#   --no-cpu-throttling         (CRITICAL: without this, Cloud Run throttles CPU
#                                outside of request handling, which kills poll loops)
#   --min-instances 1           (keeps worker alive for continuous Firestore polling)
if [ "$DEPLOY_MEDIA_WORKER" = true ]; then
    build_and_deploy \
        Dockerfile.media-worker "$SN-media-worker" . "$SN-media-worker" \
        --no-allow-unauthenticated \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 3600 \
        --min-instances 1 \
        --no-cpu-throttling
fi

# ── 4. AI Worker ────────────────────────────────────────
if [ "$DEPLOY_AI_WORKER" = true ]; then
    build_and_deploy \
        Dockerfile.ai-worker "$SN-ai-worker" . "$SN-ai-worker" \
        --no-allow-unauthenticated \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 3600 \
        --min-instances 1 \
        --no-cpu-throttling
fi

# ── Summary ──────────────────────────────────────────────
TOTAL_ELAPSED=$(( $(date +%s) - DEPLOY_START ))

# Fetch URLs for summary (may already be set from above)
API_URL=${API_URL:-$(gcloud run services describe "$SN-api" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null || echo "(not deployed)")}
FRONTEND_URL=${FRONTEND_URL:-$(gcloud run services describe "$SN-frontend" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null || echo "(not deployed)")}

echo ""
echo "========================================"
echo "Deployment complete! (${TOTAL_ELAPSED}s total)"
echo "========================================"
echo "API:            $API_URL"
echo "API Docs:       $API_URL/docs"
echo "Frontend:       $FRONTEND_URL"
echo "Media Worker:   $SN-media-worker (internal)"
echo "AI Worker:      $SN-ai-worker (internal)"
echo "========================================"
