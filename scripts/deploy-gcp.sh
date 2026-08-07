#!/bin/bash
# ==============================================================================
# deploy-gcp.sh - Automated GCP Cloud Build & Cloud Run Deployment
#
# Fully bootstraps project aug18-25-3, checks for required APIs and auto-enables
# any missing services, creates GCS buckets & Artifact Registry, initializes
# Firestore, runs Google Cloud Build, and deploys both frontend/API and worker.
#
# Usage:
#   ./deploy-gcp.sh                             # Deploy all to project aug18-25-3
#   ./deploy-gcp.sh --project aug18-25-3        # Explicit project
#   ./deploy-gcp.sh --bootstrap-only            # Bootstrap APIs & infra only
#   ./deploy-gcp.sh --service api               # Deploy API/Frontend only
#   ./deploy-gcp.sh --service worker            # Deploy Worker only
# ==============================================================================

set -eo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# ── Required GCP APIs ─────────────────────────────────────────────────────────
REQUIRED_APIS=(
    "run.googleapis.com"
    "cloudbuild.googleapis.com"
    "artifactregistry.googleapis.com"
    "firestore.googleapis.com"
    "storage.googleapis.com"
    "transcoder.googleapis.com"
    "aiplatform.googleapis.com"
    "speech.googleapis.com"
    "compute.googleapis.com"
    "bigquery.googleapis.com"
    "iam.googleapis.com"
)

# ── Parse arguments ───────────────────────────────────────────────────────────
PROJECT_ID=""
REGION="asia-south1"
SERVICE_NAME="superover"
SERVICE="all"
BOOTSTRAP_ONLY=false
SKIP_BOOTSTRAP=false
SKIP_CHECKS=true
SKIP_PRE_DEPLOY=false
USE_DOCKER=false
REPO_NAME="superover-docker"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project|-p)
            PROJECT_ID="$2"
            shift 2
            ;;
        --region|-r)
            REGION="$2"
            shift 2
            ;;
        --service|-s)
            SERVICE="$2"
            shift 2
            ;;
        --docker|--use-docker)
            USE_DOCKER=true
            shift
            ;;
        --skip-pre-deploy)
            SKIP_PRE_DEPLOY=true
            shift
            ;;
        --bootstrap-only)
            BOOTSTRAP_ONLY=true
            shift
            ;;
        --skip-bootstrap)
            SKIP_BOOTSTRAP=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./deploy-gcp.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --project, -p <PROJECT_ID>  GCP Project ID (default: aug18-25-3)"
            echo "  --region, -r <REGION>       GCP Region (default: asia-south1)"
            echo "  --service, -s <api|worker|all> Target service to deploy (default: all)"
            echo "  --docker, --use-docker      Build and push Docker containers directly without Cloud Build"
            echo "  --skip-pre-deploy           Skip linting, formatting & test pre-deploy verification"
            echo "  --bootstrap-only            Provision APIs, buckets, Firestore & IAM without deploying"
            echo "  --skip-bootstrap            Skip infra setup and run Build + Deploy directly"
            echo "  --help, -h                  Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

# Load from existing .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs 2>/dev/null || true)
fi

# Resolve PROJECT_ID fallback
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}"
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    PROJECT_ID="aug18-25-3"
fi

UPLOADS_BUCKET="${PROJECT_ID}-superover-uploads"
PROCESSED_BUCKET="${PROJECT_ID}-superover-processed"
RESULTS_BUCKET="${PROJECT_ID}-superover-results"

echo "============================================================"
echo -e "${GREEN}Super Over Alchemy - GCP Cloud Build & Deploy${NC}"
echo "============================================================"
echo "Project ID:       $PROJECT_ID"
echo "Region:           $REGION"
echo "Service Name:     $SERVICE_NAME"
echo "Target Service:   $SERVICE"
echo "Uploads Bucket:   gs://$UPLOADS_BUCKET"
echo "Processed Bucket: gs://$PROCESSED_BUCKET"
echo "Results Bucket:   gs://$RESULTS_BUCKET"
echo "============================================================"

# Ensure gcloud active project is set
gcloud config set project "$PROJECT_ID" --quiet

# ── API Validation & Auto-Enable Function ─────────────────────────────────────
ensure_apis_enabled() {
    local project="$1"
    echo -e "\n${BLUE}Checking required GCP APIs for project: $project...${NC}"
    
    local enabled_apis
    enabled_apis=$(gcloud services list --enabled --project="$project" --format="value(config.name)" 2>/dev/null || echo "")
    
    local to_enable=()
    for api in "${REQUIRED_APIS[@]}"; do
        if echo "$enabled_apis" | grep -q "^${api}$"; then
            echo -e "  ${GREEN}✓${NC} $api is enabled"
        else
            echo -e "  ${YELLOW}! $api is NOT enabled (will enable now)${NC}"
            to_enable+=("$api")
        fi
    done

    if [ ${#to_enable[@]} -gt 0 ]; then
        echo -e "\n${BLUE}Enabling ${#to_enable[@]} missing API(s)...${NC}"
        gcloud services enable "${to_enable[@]}" --project="$project" --quiet
        echo -e "${GREEN}✓ All required APIs have been successfully enabled.${NC}"
    else
        echo -e "${GREEN}✓ All ${#REQUIRED_APIS[@]} required APIs are already enabled.${NC}"
    fi
}

# ── 1. Bootstrap GCP Infrastructure ──────────────────────────────────────────
if [ "$SKIP_BOOTSTRAP" = false ]; then
    # Test and auto-enable all required APIs
    ensure_apis_enabled "$PROJECT_ID"

    echo -e "\n${BLUE}[1/4] Setting up Artifact Registry Docker repository...${NC}"
    if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
        gcloud artifacts repositories create "$REPO_NAME" \
            --repository-format=docker \
            --location="$REGION" \
            --project="$PROJECT_ID" \
            --description="Docker repository for Super Over Alchemy services" \
            --quiet
        echo "Created Artifact Registry repository: $REPO_NAME in $REGION"
    else
        echo "Artifact Registry repository $REPO_NAME already exists in $REGION"
    fi

    echo -e "\n${BLUE}[2/4] Setting up Cloud Storage Buckets & CORS...${NC}"
    for b in "$UPLOADS_BUCKET" "$PROCESSED_BUCKET" "$RESULTS_BUCKET"; do
        if ! gsutil ls -b "gs://$b" >/dev/null 2>&1; then
            echo "Creating bucket gs://$b..."
            gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$b" || true
        else
            echo "Bucket gs://$b already exists"
        fi
    done

    # Apply CORS JSON on uploads bucket for direct signed URL browser uploads
    cat << 'EOF' > /tmp/superover_cors.json
[
  {
    "origin": ["*"],
    "method": ["GET", "PUT", "POST", "HEAD", "OPTIONS"],
    "responseHeader": ["Content-Type", "x-goog-resumable", "x-goog-meta-*", "Authorization"],
    "maxAgeSeconds": 3600
  }
]
EOF
    gsutil cors set /tmp/superover_cors.json "gs://$UPLOADS_BUCKET" || true
    rm -f /tmp/superover_cors.json

    echo -e "\n${BLUE}[3/4] Initializing Firestore Native Database...${NC}"
    if ! gcloud firestore databases describe --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo "Creating Firestore (default) database in $REGION..."
        gcloud firestore databases create --location="$REGION" --project="$PROJECT_ID" --type=firestore-native --quiet || true
    else
        echo "Firestore database already initialized"
    fi

    echo -e "\n${BLUE}[4/4] Configuring IAM Service Account Permissions...${NC}"
    PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
    COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
    CLOUDBUILD_SA="${PROJECT_NUM}@cloudbuild.gserviceaccount.com"

    ROLES=(
        "roles/datastore.user"
        "roles/storage.objectAdmin"
        "roles/aiplatform.user"
        "roles/speech.client"
        "roles/transcoder.admin"
    )

    for role in "${ROLES[@]}"; do
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$COMPUTE_SA" \
            --role="$role" \
            --condition=None --quiet >/dev/null 2>&1 || true
    done

    # Grant Cloud Build permission to deploy to Cloud Run and pull from Artifact Registry
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$CLOUDBUILD_SA" \
        --role="roles/run.admin" \
        --condition=None --quiet >/dev/null 2>&1 || true
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$CLOUDBUILD_SA" \
        --role="roles/iam.serviceAccountUser" \
        --condition=None --quiet >/dev/null 2>&1 || true
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$CLOUDBUILD_SA" \
        --role="roles/artifactregistry.writer" \
        --condition=None --quiet >/dev/null 2>&1 || true

    echo -e "${GREEN}✓ GCP Infrastructure Bootstrapping Complete.${NC}"
fi

# Write updated .env file locally
cat << EOF > .env
GCP_PROJECT_ID=$PROJECT_ID
GCP_REGION=$REGION
SERVICE_NAME=$SERVICE_NAME
UPLOADS_BUCKET=$UPLOADS_BUCKET
PROCESSED_BUCKET=$PROCESSED_BUCKET
RESULTS_BUCKET=$RESULTS_BUCKET
FIRESTORE_DATABASE=(default)
ENVIRONMENT=production
TRANSCODER_LOCATION=$REGION
GEMINI_REGION=global
GEMINI_DEFAULT_MODEL=gemini-3.1-pro-preview
GEMINI_SEARCH_MODEL=gemini-3.5-flash
SEARCH_BACKEND=bigquery
EOF
echo -e "\n${GREEN}Saved project configuration to .env (Project: $PROJECT_ID)${NC}"

if [ "$BOOTSTRAP_ONLY" = true ]; then
    echo -e "\n${GREEN}Bootstrap-only mode completed. Exiting without build/deploy.${NC}"
    exit 0
fi

# ── 2. Run Pre-Deployment Verification (Lint, Types, Tests, Build) ───────────
if [ "$SKIP_PRE_DEPLOY" = false ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/pre-deploy.sh" ]; then
        echo -e "\n${BLUE}Running pre-deployment verification pipeline...${NC}"
        "$SCRIPT_DIR/pre-deploy.sh"
    fi
fi

# ── 3. Build and Push Container Images ──────────────────────────────────────
IMAGE_REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

if [ "$USE_DOCKER" = true ]; then
    echo -e "\n${BLUE}Building container images natively with Docker...${NC}"
    echo "Configuring Docker authentication for Artifact Registry in $REGION..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

    if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "api" ]; then
        echo -e "\n${BLUE}Building $REPO_NAME/superover-frontend:$COMMIT_SHA...${NC}"
        docker build -f Dockerfile.api \
            -t "$IMAGE_REGISTRY/superover-frontend:$COMMIT_SHA" \
            -t "$IMAGE_REGISTRY/superover-frontend:latest" \
            .
        echo "Pushing frontend image to Artifact Registry..."
        docker push "$IMAGE_REGISTRY/superover-frontend:$COMMIT_SHA"
        docker push "$IMAGE_REGISTRY/superover-frontend:latest"
    fi

    if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "worker" ]; then
        echo -e "\n${BLUE}Building $REPO_NAME/superover-worker:$COMMIT_SHA...${NC}"
        docker build -f Dockerfile.worker \
            -t "$IMAGE_REGISTRY/superover-worker:$COMMIT_SHA" \
            -t "$IMAGE_REGISTRY/superover-worker:latest" \
            .
        echo "Pushing worker image to Artifact Registry..."
        docker push "$IMAGE_REGISTRY/superover-worker:$COMMIT_SHA"
        docker push "$IMAGE_REGISTRY/superover-worker:latest"
    fi
else
    echo -e "\n${BLUE}Submitting build to Google Cloud Build in project $PROJECT_ID...${NC}"
    gcloud builds submit \
        --config=cloudbuild.yaml \
        --substitutions=_REGION="$REGION",_REPO_NAME="$REPO_NAME",COMMIT_SHA="$COMMIT_SHA" \
        --project="$PROJECT_ID" \
        .
fi

# ── 3. Deploy to Cloud Run (gen2) ─────────────────────────────────────────────
BACKEND_ENVS="GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=$REGION,\
ENVIRONMENT=production,\
UPLOADS_BUCKET=$UPLOADS_BUCKET,\
PROCESSED_BUCKET=$PROCESSED_BUCKET,\
RESULTS_BUCKET=$RESULTS_BUCKET,\
FIRESTORE_DATABASE=(default),\
SERVICE_NAME=$SERVICE_NAME,\
TRANSCODER_LOCATION=$REGION,\
GEMINI_REGION=global,\
GEMINI_DEFAULT_MODEL=gemini-3.1-pro-preview,\
GEMINI_SEARCH_MODEL=gemini-3.5-flash,\
SEARCH_BACKEND=bigquery,\
MASTER_INVITE_CODE=${MASTER_INVITE_CODE:-8d109791302dc0d0f693263f1f55c939}"

if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "api" ]; then
    echo -e "\n${BLUE}Deploying $SERVICE_NAME-frontend to Cloud Run...${NC}"
    gcloud run deploy "$SERVICE_NAME-frontend" \
        --image "$IMAGE_REGISTRY/superover-frontend:$COMMIT_SHA" \
        --platform managed \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --execution-environment gen2 \
        --allow-unauthenticated \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 300 \
        --quiet
fi

if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "worker" ]; then
    echo -e "\n${BLUE}Deploying $SERVICE_NAME-worker to Cloud Run...${NC}"
    gcloud run deploy "$SERVICE_NAME-worker" \
        --image "$IMAGE_REGISTRY/superover-worker:$COMMIT_SHA" \
        --platform managed \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --execution-environment gen2 \
        --no-allow-unauthenticated \
        --no-cpu-throttling \
        --set-env-vars "$BACKEND_ENVS" \
        --cpu 4 \
        --memory 8Gi \
        --timeout 3600 \
        --quiet
fi

# ── 4. Completion Summary ─────────────────────────────────────────────────────
FRONTEND_URL=$(gcloud run services describe "$SERVICE_NAME-frontend" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null || echo "(not deployed)")

echo ""
echo "============================================================"
echo -e "${GREEN}🎉 Deployment Successfully Completed on $PROJECT_ID!${NC}"
echo "============================================================"
echo -e "Web App & REST API: ${GREEN}$FRONTEND_URL${NC}"
echo -e "Interactive Docs:   ${GREEN}$FRONTEND_URL/docs${NC}"
echo -e "Background Worker:  ${GREEN}$SERVICE_NAME-worker (internal, unthrottled)${NC}"
echo "============================================================"
