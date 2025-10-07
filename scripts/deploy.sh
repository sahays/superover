#!/bin/bash

# Super Over Alchemy - Unified Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
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

# --- Main Deployment ---
main() {
    local target_module=""

    # --- Parse Command Line Arguments ---
    while [[ $# -gt 0 ]]; do
        case $1 in
            --target)
                if [[ -n "$2" ]]; then
                    target_module="$2"
                    shift 2
                else
                    log_error "Error: --target requires a module name."
                    exit 1
                fi
                ;;
            --help)
                echo "Usage: $0 [--target <module_name>]"
                echo "  --target: Deploy only a specific service module (e.g., scene_analyzer_worker)."
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    echo "======================================================"
    echo "Super Over Alchemy - Unified Declarative Deployment"
    echo "======================================================"
    
    if [[ -n "$target_module" ]]; then
        log_info "This script will perform a TARGETED deployment for module: $target_module"
    else
        log_info "This script will deploy the ENTIRE application infrastructure."
    fi
    
    log_info "Ensure you have run './scripts/build-and-push.sh' first to build your container images."
    echo ""

    cd terraform

    log_info "Initializing Terraform..."
    if ! terraform init; then
        log_error "Terraform init failed."
        exit 1
    fi

    # Build the apply command
    local apply_cmd="terraform apply -auto-approve"
    if [[ -n "$target_module" ]]; then
        apply_cmd+=" -target=\"module.$target_module\""
    fi

    log_info "Applying Terraform configuration..."
    # Use eval to correctly handle the quoted -target argument
    if ! eval "$apply_cmd"; then
        log_error "Terraform apply failed."
        exit 1
    fi
    
    log_success "Terraform apply completed successfully."
    cd ..

    # Run post-configuration script to update GCS CORS
    log_info "Running post-configuration script..."
    if ./scripts/configure-post-terraform.sh; then
        log_success "Post-configuration completed successfully."
    else
        log_error "Post-configuration failed. Please run './scripts/configure-post-terraform.sh' manually."
    fi

    echo "=============================================="
    log_success "Deployment completed successfully!"
    echo ""
    log_info "Service URLs:"
    echo "  Frontend: Run 'gcloud run services describe frontend-service --region=\$GCP_REGION --format=\"value(status.url)\"'"
    echo "  API:      Run 'gcloud run services describe api-service --region=\$GCP_REGION --format=\"value(status.url)\"'"
    echo ""
    log_info "Next steps:"
    echo "  1. Build and push container images: ./scripts/build-and-push.sh"
    echo "  2. Access your application at the frontend URL above"
    echo "=============================================="
}

main "$@"