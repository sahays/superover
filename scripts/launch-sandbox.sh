#!/bin/bash
# ==============================================================================
# launch-sandbox.sh - Launch and bootstrap a remote GCP Sandbox GCE VM
#
# Creates an authentic Linux testing VM in project aug18-25-3 on host-vpc / gke-subnet
# with Docker, Python 3.12, Node.js, and GCP ADC credentials.
#
# Usage:
#   ./launch-sandbox.sh                            # Launch sandbox in aug18-25-3
#   ./launch-sandbox.sh --project aug18-25-3       # Explicit project
#   ./launch-sandbox.sh --delete                   # Delete sandbox VM
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
MACHINE_TYPE="e2-standard-4"
VM_NAME="superover-sandbox-vm"
DELETE_VM=false

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
        --machine-type|-m)
            MACHINE_TYPE="$2"
            shift 2
            ;;
        --name|-n)
            VM_NAME="$2"
            shift 2
            ;;
        --delete|-d)
            DELETE_VM=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./launch-sandbox.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --project, -p <PROJECT_ID>  GCP Project ID (default: aug18-25-3)"
            echo "  --zone, -z <ZONE>           GCE Zone (default: asia-south1-a)"
            echo "  --machine-type, -m <TYPE>   Machine type (default: e2-standard-4)"
            echo "  --name, -n <VM_NAME>        Instance name (default: superover-sandbox-vm)"
            echo "  --delete, -d                Delete the sandbox VM"
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

# Detect VPC Network & Subnet
NETWORK=$(gcloud compute networks list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | head -n 1 || echo "default")
REGION="${ZONE%-*}"
SUBNET=$(gcloud compute networks subnets list --network="$NETWORK" --project="$PROJECT_ID" --filter="region:$REGION" --format="value(name)" 2>/dev/null | head -n 1 || echo "")

echo "============================================================"
echo -e "${GREEN}Super Over Alchemy - Sandbox VM Manager${NC}"
echo "============================================================"
echo "Project:      $PROJECT_ID"
echo "VM Name:      $VM_NAME"
echo "Zone:         $ZONE"
echo "Network:      $NETWORK"
echo "Subnet:       ${SUBNET:-default}"
echo "Machine Type: $MACHINE_TYPE"
echo "============================================================"

# Handle VM Teardown
if [ "$DELETE_VM" = true ]; then
    echo -e "\n${YELLOW}Deleting sandbox VM: $VM_NAME in zone $ZONE...${NC}"
    gcloud compute instances delete "$VM_NAME" \
        --zone="$ZONE" \
        --project="$PROJECT_ID" \
        --quiet || true
    echo -e "${GREEN}Sandbox VM successfully deleted.${NC}"
    exit 0
fi

# Check if VM already exists
if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo -e "\n${YELLOW}VM $VM_NAME is already running in $ZONE.${NC}"
else
    echo -e "\n${BLUE}Creating dedicated testing sandbox VM $VM_NAME in $ZONE...${NC}"
    
    STARTUP_SCRIPT=$(cat << 'EOF'
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git build-essential ffmpeg software-properties-common

# Install Docker CE
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes || true
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

usermod -aG docker ubuntu || true
chmod 666 /var/run/docker.sock || true

# Install Python 3.12
add-apt-repository -y ppa:deadsnakes/ppa || true
apt-get update -y
apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 || true

# Install Node.js 18 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

echo "=== Sandbox VM Initialization Complete ==="
EOF
)

    SUBNET_ARG=""
    if [ -n "$SUBNET" ]; then
        SUBNET_ARG="--subnet=$SUBNET"
    fi

    gcloud compute instances create "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" \
        --network="$NETWORK" \
        $SUBNET_ARG \
        --no-address \
        --shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring \
        --image-family="ubuntu-2204-lts" \
        --image-project="ubuntu-os-cloud" \
        --boot-disk-size="50GB" \
        --boot-disk-type="pd-ssd" \
        --scopes="https://www.googleapis.com/auth/cloud-platform" \
        --metadata=startup-script="$STARTUP_SCRIPT" \
        --quiet

    echo -e "${GREEN}VM created. Waiting 25s for initialization...${NC}"
    sleep 25
fi

# Sync workspace source code to remote VM
echo -e "\n${BLUE}Syncing workspace files to remote VM ($VM_NAME)...${NC}"
gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="mkdir -p ~/super-over-alchemy" --quiet

tar --exclude='.git' --exclude='node_modules' --exclude='dist' --exclude='venv' --exclude='storage/temp' \
    -czf /tmp/superover_workspace.tar.gz .

gcloud compute scp /tmp/superover_workspace.tar.gz "$VM_NAME:~/superover_workspace.tar.gz" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --quiet

gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="tar -xzf ~/superover_workspace.tar.gz -C ~/super-over-alchemy && rm -f ~/superover_workspace.tar.gz" \
    --quiet
rm -f /tmp/superover_workspace.tar.gz

echo ""
echo "============================================================"
echo -e "${GREEN}✓ Remote Sandbox VM ($VM_NAME) is ready in $PROJECT_ID!${NC}"
echo "============================================================"
echo "To connect to your VM via SSH:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
echo ""
echo "To run automated remote tests on this VM:"
echo "  ./remote-test.sh --project $PROJECT_ID"
echo "============================================================"
