#!/bin/bash
# ==============================================================================
# remote-test.sh - Run integration tests and container builds on Sandbox VM
#
# Syncs local code changes, verifies GCP APIs, and executes test suites inside the
# remote GCE sandbox VM in project aug18-25-3 with native Linux & Docker daemon.
#
# Usage:
#   ./remote-test.sh                             # Run all tests remotely on aug18-25-3
#   ./remote-test.sh --project aug18-25-3        # Explicit project
#   ./remote-test.sh --test api                  # Run API tests
#   ./remote-test.sh --test worker               # Run Worker tests
#   ./remote-test.sh --test libs                 # Run Library tests
#   ./remote-test.sh --test docker               # Validate Dockerfile builds natively
#   ./remote-test.sh --test frontend             # Validate Vite SPA build
# ==============================================================================

set -eo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

REQUIRED_APIS=(
    "compute.googleapis.com"
    "storage.googleapis.com"
    "firestore.googleapis.com"
    "aiplatform.googleapis.com"
    "speech.googleapis.com"
    "transcoder.googleapis.com"
)

PROJECT_ID=""
ZONE="asia-south1-a"
VM_NAME=""
TEST_TYPE="all"
SYNC_CODE=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project|-p)
            PROJECT_ID="$2"
            shift 2
            ;;
        --zone|-z)
            ZONE="$2"
            shift 2
            ;;
        --vm|-v)
            VM_NAME="$2"
            shift 2
            ;;
        --test|-t)
            TEST_TYPE="$2"
            shift 2
            ;;
        --no-sync)
            SYNC_CODE=false
            shift
            ;;
        --help|-h)
            echo "Usage: ./remote-test.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --test, -t <api|worker|libs|unit|docker|frontend|all> Test suite to run (default: all)"
            echo "  --project, -p <PROJECT_ID>  GCP Project ID (default: aug18-25-3)"
            echo "  --zone, -z <ZONE>           GCE Zone (default: asia-south1-a or discovered zone)"
            echo "  --vm, -v <VM_NAME>          Sandbox VM name (auto-discovered if omitted)"
            echo "  --no-sync                   Skip syncing local files before test"
            echo "  --help, -h                  Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

if [ -z "$PROJECT_ID" ]; then
    if [ -f .env ]; then
        PROJECT_ID=$(grep -E '^GCP_PROJECT_ID=' .env | cut -d '=' -f2 | tr -d ' "' || true)
    fi
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "aug18-25-3")
    fi
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    PROJECT_ID="aug18-25-3"
fi

gcloud config set project "$PROJECT_ID" --quiet

# ── API Validation & Auto-Enable Function ─────────────────────────────────────
echo -e "\n${BLUE}Verifying required GCP APIs for project: $PROJECT_ID...${NC}"
ENABLED_APIS=$(gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" 2>/dev/null || echo "")

TO_ENABLE=()
for api in "${REQUIRED_APIS[@]}"; do
    if echo "$ENABLED_APIS" | grep -q "^${api}$"; then
        echo -e "  ${GREEN}✓${NC} $api is enabled"
    else
        echo -e "  ${YELLOW}! $api is NOT enabled (will enable now)${NC}"
        TO_ENABLE+=("$api")
    fi
done

if [ ${#TO_ENABLE[@]} -gt 0 ]; then
    echo -e "${BLUE}Enabling ${#TO_ENABLE[@]} missing API(s)...${NC}"
    gcloud services enable "${TO_ENABLE[@]}" --project="$PROJECT_ID" --quiet
    echo -e "${GREEN}✓ Required APIs enabled.${NC}"
fi

# ── Auto-Discover VM Name and Zone ─────────────────────────────────────────────
if [ -z "$VM_NAME" ]; then
    RUNNING_VMS=$(gcloud compute instances list --project="$PROJECT_ID" --filter="status=RUNNING" --format="value(name,zone)" 2>/dev/null || echo "")
    if [ -n "$RUNNING_VMS" ]; then
        VM_NAME=$(echo "$RUNNING_VMS" | head -n 1 | awk '{print $1}')
        DISCOVERED_ZONE=$(echo "$RUNNING_VMS" | head -n 1 | awk '{print $2}')
        if [ -n "$DISCOVERED_ZONE" ]; then
            ZONE="$DISCOVERED_ZONE"
        fi
        echo -e "${GREEN}Auto-discovered sandbox VM: $VM_NAME (Zone: $ZONE)${NC}"
    else
        VM_NAME="superover-sandbox-vm"
    fi
fi

echo "============================================================"
echo -e "${GREEN}Super Over Alchemy - Remote Sandbox Test Runner${NC}"
echo "============================================================"
echo "Project:   $PROJECT_ID"
echo "VM Name:   $VM_NAME"
echo "Zone:      $ZONE"
echo "Test Type: $TEST_TYPE"
echo "============================================================"

# Ensure VM exists
if ! gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo -e "${RED}Sandbox VM $VM_NAME was not found in zone $ZONE.${NC}"
    echo "Run ./launch-sandbox.sh to provision or verify your sandbox VM."
    exit 1
fi

# ── 1. Sync Code to VM ───────────────────────────────────────────────────────
if [ "$SYNC_CODE" = true ]; then
    echo -e "\n${BLUE}Syncing workspace changes to $VM_NAME...${NC}"
    tar --exclude='.git' --exclude='node_modules' --exclude='dist' --exclude='venv' --exclude='storage/temp' \
        -czf /tmp/superover_test_sync.tar.gz .

    gcloud compute scp /tmp/superover_test_sync.tar.gz "$VM_NAME:~/superover_test_sync.tar.gz" \
        --zone="$ZONE" \
        --project="$PROJECT_ID" \
        --quiet

    gcloud compute ssh "$VM_NAME" \
        --zone="$ZONE" \
        --project="$PROJECT_ID" \
        --command="mkdir -p ~/super-over-alchemy && tar -xzf ~/superover_test_sync.tar.gz -C ~/super-over-alchemy && rm -f ~/superover_test_sync.tar.gz" \
        --quiet
    rm -f /tmp/superover_test_sync.tar.gz
    echo -e "${GREEN}Code sync complete.${NC}"
fi

# ── 2. Run Test Command on Sandbox VM ─────────────────────────────────────────
echo -e "\n${BLUE}Executing remote test suite on Linux VM [$TEST_TYPE]...${NC}"

gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="
set -e
cd ~/super-over-alchemy

# Ensure python venv package, libGL, Node.js 20, and build tools are installed on Linux
if [ ! -f /usr/local/bin/node ]; then
    echo '>> Installing Node.js 20 LTS binary to /usr/local...'
    curl -fsSL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz | sudo tar -xJ -C /usr/local --strip-components=1
    sudo rm -f /usr/bin/node /usr/bin/npm /usr/bin/npx
    sudo ln -sf /usr/local/bin/node /usr/bin/node
    sudo ln -sf /usr/local/bin/npm /usr/bin/npm
    sudo ln -sf /usr/local/bin/npx /usr/bin/npx
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3.10-venv python3-pip python3-full build-essential libgl1 libglib2.0-0 ffmpeg
fi

# Set up Python virtual environment if missing
if [ ! -d 'venv' ] || [ ! -f 'venv/bin/activate' ]; then
    echo '>> Creating Python venv on sandbox VM...'
    rm -rf venv
    python3 -m venv venv
fi
source venv/bin/activate
echo '>> Installing test dependencies...'
pip install -r requirements.txt -r requirements-test.txt

case '$TEST_TYPE' in
    api)
        echo '>> Running API test suite...'
        pytest tests/api/ -v
        ;;
    worker)
        echo '>> Running Worker test suite...'
        pytest tests/workers/ -v
        ;;
    libs)
        echo '>> Running Libraries test suite...'
        pytest tests/libs/ -v
        ;;
    unit)
        echo '>> Running Unit test suite...'
        pytest -m unit -v
        ;;
    docker)
        echo '>> Validating Docker container builds natively on Linux...'
        docker build -f Dockerfile.api -t test-frontend .
        docker build -f Dockerfile.worker -t test-worker .
        echo 'Docker builds succeeded!'
        ;;
    frontend)
        echo '>> Building Vite frontend SPA...'
        cd frontend && npm install && npm run build
        echo 'Frontend build succeeded!'
        ;;
    all)
        echo '>> Running all pytest suites...'
        pytest tests/ -v
        echo '>> Validating frontend build...'
        cd frontend && npm install && npm run build
        echo 'All tests succeeded!'
        ;;
esac
"

echo ""
echo "============================================================"
echo -e "${GREEN}✓ Remote tests on $PROJECT_ID completed successfully!${NC}"
echo "============================================================"
