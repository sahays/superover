#!/bin/bash

# Super Over Alchemy - Cleanup Script
# Destroys all infrastructure and cleans up resources

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
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

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Parse arguments
FORCE=false
KEEP_IMAGES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
            shift
            ;;
        --keep-images)
            KEEP_IMAGES=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --force        Skip confirmation prompts"
            echo "  --keep-images  Don't delete container images"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Confirmation
confirm_cleanup() {
    if [[ "$FORCE" != true ]]; then
        echo "=============================================="
        log_warn "This will destroy ALL Super Over Alchemy infrastructure!"
        log_warn "This includes:"
        echo "  - Cloud Run services"
        echo "  - Pub/Sub topics and subscriptions"
        echo "  - Storage buckets (and all data)"
        echo "  - Firestore database"
        echo "  - Service accounts"
        echo "  - Artifact Registry repository"
        echo "=============================================="
        read -p "Are you sure you want to continue? (type 'yes' to confirm): " response

        if [[ "$response" != "yes" ]]; then
            log_info "Cleanup cancelled"
            exit 0
        fi
    fi
}

# Destroy infrastructure
destroy_infrastructure() {
    log_info "Destroying infrastructure with Terraform..."

    cd terraform

    if [[ ! -f "terraform.tfvars" ]]; then
        log_error "terraform/terraform.tfvars not found"
        exit 1
    fi

    # Remove Firestore database from Terraform state first (it requires special deletion handling)
    log_info "Removing Firestore database from Terraform state..."
    terraform state rm google_firestore_database.database 2>/dev/null || log_warn "Firestore database not in state"

    # Run terraform destroy (everything except Firestore)
    log_info "Running terraform destroy..."
    if ! terraform destroy -auto-approve; then
        log_error "Terraform destroy failed"
        log_warn "You may need to manually clean up some resources"
        exit 1
    fi

    # Now manually delete the Firestore database
    log_info "Manually deleting Firestore database..."
    if gcloud firestore databases delete --database="(default)" --quiet 2>/dev/null; then
        log_success "Firestore database deleted"
    elif gcloud firestore databases describe --database="(default)" >/dev/null 2>&1; then
        log_warn "Firestore database exists but could not be deleted automatically"
        log_info "Manual deletion command: gcloud firestore databases delete --database='(default)'"
        log_info "Or go to: https://console.cloud.google.com/firestore/databases"
    else
        log_info "No Firestore database found to delete"
    fi

    cd ..
    log_success "Infrastructure destroyed"
}

# Clean up images (skipped since we use Cloud Build)
cleanup_images() {
    if [[ "$KEEP_IMAGES" == true ]]; then
        log_info "Skipping image cleanup (--keep-images specified)"
        return
    fi

    log_info "Skipping local Docker image cleanup (using Cloud Build)"
    log_info "Container images in Artifact Registry will be cleaned up with infrastructure"

    log_success "Image cleanup completed"
}

# Main cleanup
main() {
    echo "=============================================="
    echo "Super Over Alchemy - Cleanup"
    echo "=============================================="

    confirm_cleanup
    destroy_infrastructure
    cleanup_images

    echo "=============================================="
    log_success "Cleanup completed!"
    echo ""
    log_info "All Super Over Alchemy resources have been removed."
    log_info "Don't forget to check for any manual cleanup needed in:"
    echo "  - Cloud Console for any remaining resources"
    echo "  - Billing to ensure no unexpected charges"
    echo "=============================================="
}

main "$@"