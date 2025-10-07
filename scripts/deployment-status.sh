#!/bin/bash

# Super Over Alchemy - Status and URLs Script
# Displays deployment status and application URLs

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration - read from .env file
if [[ -f ".env" ]]; then
    export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID=${PROJECT_ID:-${GCP_PROJECT_ID:-$(gcloud config get-value project)}}
REGION=${REGION:-${GCP_REGION:-us-central1}}

echo "=============================================="
echo "  Super Over Alchemy - Deployment Status"
echo "=============================================="
echo ""

# Get Load Balancer IP
LB_IP=$(gcloud compute addresses list --global --project="$PROJECT_ID" --filter="name=frontend-lb-ip" --format="value(address)" 2>/dev/null || echo "")

if [[ -n "$LB_IP" ]]; then
    DOMAIN="${LB_IP//./-}.sslip.io"
    echo -e "${GREEN}🌐 Application URLs${NC}"
    echo "   Frontend: https://$DOMAIN"
    echo "   API:      https://$DOMAIN/api"
    echo ""
fi

# Get Cloud Run Services
echo -e "${BLUE}☁️  Cloud Run Services${NC}"
gcloud run services list --region="$REGION" --project="$PROJECT_ID" --format="table[box](name,status.url)" 2>/dev/null || echo "   No services found"
echo ""

# Get Cloud Run Jobs
echo -e "${BLUE}⚙️  Cloud Run Jobs${NC}"
gcloud run jobs list --region="$REGION" --project="$PROJECT_ID" --format="table[box](name,status.conditions[0].status)" 2>/dev/null || echo "   No jobs found"
echo ""

# Get Storage Buckets
echo -e "${BLUE}🗄️  Storage Buckets${NC}"
echo "   Raw uploads:       gs://$(echo $RAW_UPLOADS_BUCKET_NAME)"
echo "   Processed outputs: gs://$(echo $PROCESSED_OUTPUTS_BUCKET_NAME)"
echo ""

# Get Pub/Sub Status
echo -e "${BLUE}📨 Pub/Sub${NC}"
TOPIC_EXISTS=$(gcloud pubsub topics list --project="$PROJECT_ID" --filter="name:scene-analysis-jobs" --format="value(name)" 2>/dev/null || echo "")
if [[ -n "$TOPIC_EXISTS" ]]; then
    echo "   Topic:        scene-analysis-jobs ✓"
    SUB_EXISTS=$(gcloud pubsub subscriptions list --project="$PROJECT_ID" --filter="name:scene-analysis-jobs-push-sub" --format="value(name)" 2>/dev/null || echo "")
    if [[ -n "$SUB_EXISTS" ]]; then
        echo "   Subscription: scene-analysis-jobs-push-sub ✓"
    fi
else
    echo "   Not configured"
fi
echo ""

# Terraform Outputs
echo -e "${BLUE}📊 Terraform State${NC}"
if [[ -f "terraform/terraform.tfstate" ]]; then
    cd terraform
    OUTPUTS=$(terraform output 2>&1)
    if echo "$OUTPUTS" | grep -q "No outputs found"; then
        echo "   No outputs defined"
    else
        echo "$OUTPUTS"
    fi
    cd ..
else
    echo "   terraform.tfstate not found"
fi
echo ""

echo "=============================================="
echo -e "${GREEN}✓ Status check complete${NC}"
echo "=============================================="
