#!/bin/bash
# ==============================================================================
# deploy-sandbox.sh - Deploy to Cloud Run using Docker on the Sandbox VM
#
# Syncs code to superover-sandbox-vm, builds multi-stage containers directly
# inside the VM via Docker, pushes images to Artifact Registry, and deploys
# both superover-frontend (API + UI) and superover-worker to Cloud Run.
#
# Usage:
#   ./deploy-sandbox.sh                         # Deploy to aug18-25-3
#   ./deploy-sandbox.sh --service api           # Deploy frontend/API only
#   ./deploy-sandbox.sh --service worker        # Deploy worker only
# ==============================================================================

set -eo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID=""
ZONE="asia-south1-a"
REGION="asia-south1"
VM_NAME="superover-sandbox-vm"
SERVICE="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project|-p)
            PROJECT_ID="$2"
            shift 2
            ;;
        --vm)
            VM_NAME="$2"
            shift 2
            ;;
        --zone|-z)
            ZONE="$2"
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
        --help|-h)
            echo "Usage: ./deploy-sandbox.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --project, -p <PROJECT_ID>  GCP Project ID (default: aug18-25-3)"
            echo "  --vm <VM_NAME>              Sandbox VM name (default: superover-sandbox-vm)"
            echo "  --zone, -z <ZONE>           GCP Zone (default: asia-south1-a)"
            echo "  --region, -r <REGION>       GCP Region (default: asia-south1)"
            echo "  --service, -s <api|worker|all> Target service to deploy (default: all)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}"
fi
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    PROJECT_ID="aug18-25-3"
fi

gcloud config set project "$PROJECT_ID" --quiet

echo "============================================================"
echo -e "${GREEN}Super Over Alchemy - Sandbox VM Docker Deploy${NC}"
echo "============================================================"
echo "Project:   $PROJECT_ID"
echo "VM Name:   $VM_NAME"
echo "Zone:      $ZONE"
echo "Region:    $REGION"
echo "Service:   $SERVICE"
echo "============================================================"

# Ensure VM is running
VM_STATUS=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format='value(status)' 2>/dev/null || echo "NOT_FOUND")
if [ "$VM_STATUS" != "RUNNING" ]; then
    echo -e "${YELLOW}VM $VM_NAME is in status: $VM_STATUS. Starting VM...${NC}"
    gcloud compute instances start "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --quiet
    echo -e "${GREEN}✓ VM started successfully.${NC}"
fi

echo -e "\n${BLUE}Syncing workspace changes to $VM_NAME...${NC}"
ARCHIVE_PATH="/tmp/superover_deploy_$(date +%s).tar.gz"
tar --exclude='.git' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='node_modules' \
    --exclude='.pytest_cache' \
    --exclude='dist' \
    --exclude='.coverage' \
    -czf "$ARCHIVE_PATH" .

gcloud compute scp \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --tunnel-through-iap \
    "$ARCHIVE_PATH" "${VM_NAME}:~/workspace_deploy.tar.gz"

rm -f "$ARCHIVE_PATH"

gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --tunnel-through-iap \
    --command "mkdir -p ~/super-over-alchemy && tar -xzf ~/workspace_deploy.tar.gz -C ~/super-over-alchemy && rm -f ~/workspace_deploy.tar.gz"

echo -e "${GREEN}Code sync complete.${NC}"

echo -e "\n${BLUE}Executing Docker build and Cloud Run deployment on $VM_NAME...${NC}"
gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --tunnel-through-iap \
    --command "bash -c '
set -e
cd ~/super-over-alchemy

# Ensure docker is installed and running
if ! command -v docker >/dev/null 2>&1; then
    echo \">> Installing docker.io on sandbox VM...\"
    while sudo fuser /var/lib/dpkg/lock >/dev/null 2>&1 || sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1 || sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
        sleep 2
    done
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker \$USER
fi

# Ensure docker daemon is running
sudo systemctl is-active --quiet docker || sudo systemctl start docker
sudo chmod 666 /var/run/docker.sock 2>/dev/null || true

# Run deployment script using Docker (skipping API bootstrap already completed by admin)
chmod +x ./deploy-gcp.sh
./deploy-gcp.sh --project $PROJECT_ID --region $REGION --service $SERVICE --docker --skip-bootstrap
'"

echo ""
echo "============================================================"
echo -e "${GREEN}✓ Deployment via Sandbox VM completed successfully!${NC}"
echo "============================================================"
