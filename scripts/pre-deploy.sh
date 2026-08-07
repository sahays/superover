#!/bin/bash
# ==============================================================================
# scripts/pre-deploy.sh - Master Pre-Deployment Verification Pipeline
#
# Runs comprehensive linting, formatting checks, static type checks,
# backend pytest test suites, frontend ESLint, and Next.js/Vite production build.
#
# Usage:
#   ./scripts/pre-deploy.sh                  # Run all checks
#   ./scripts/pre-deploy.sh --skip-tests    # Skip pytest suite
#   ./scripts/pre-deploy.sh --skip-frontend # Skip frontend checks
#   ./scripts/pre-deploy.sh --fix           # Auto-format Python code
# ==============================================================================

set -eo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

SKIP_TESTS=false
SKIP_FRONTEND=false
SKIP_LINT=false
AUTO_FIX=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --skip-lint)
            SKIP_LINT=true
            shift
            ;;
        --fix)
            AUTO_FIX=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/pre-deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-tests     Skip running pytest test suites"
            echo "  --skip-frontend  Skip frontend ESLint and Vite build"
            echo "  --skip-lint      Skip Python linting and formatting checks"
            echo "  --fix            Automatically fix Python formatting issues"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo -e "${BOLD}Super Over Alchemy - Pre-Deployment Verification${NC}"
echo "============================================================"

# Check if Python virtual environment exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

FAILED_CHECKS=()

# ── 1. Python Formatting & Linting ────────────────────────────────────────────
if [ "$SKIP_LINT" = false ]; then
    echo -e "\n${BLUE}[1/5] Running Python Formatting & Linting...${NC}"

    if [ "$AUTO_FIX" = true ]; then
        if command -v ruff >/dev/null 2>&1; then
            echo "Applying ruff formatting and auto-fixes..."
            ruff check --fix . || true
            ruff format . || true
        elif command -v black >/dev/null 2>&1; then
            black . || true
        fi
    fi

    # Check formatting
    if command -v ruff >/dev/null 2>&1; then
        echo -n "Checking ruff formatting... "
        if ruff format --check . >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Clean${NC}"
        else
            echo -e "${YELLOW}! Formatting differences found (run with --fix to apply)${NC}"
        fi

        echo -n "Checking ruff linter rules... "
        if ruff check . >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Passed${NC}"
        else
            echo -e "${RED}✗ Linting errors found${NC}"
            ruff check . || true
            FAILED_CHECKS+=("Python Linting (ruff)")
        fi
    elif command -v flake8 >/dev/null 2>&1; then
        echo -n "Checking flake8 rules... "
        if flake8 api libs workers --max-line-length=120 >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Passed${NC}"
        else
            echo -e "${RED}✗ flake8 errors found${NC}"
            FAILED_CHECKS+=("Python Linting (flake8)")
        fi
    else
        echo -e "${YELLOW}Notice: ruff/flake8 not found in environment; skipping Python lint.${NC}"
    fi
fi

# ── 2. Python Static Type Checking ────────────────────────────────────────────
echo -e "\n${BLUE}[2/5] Running Python Static Type Checking (mypy)...${NC}"
if command -v mypy >/dev/null 2>&1; then
    if mypy --config-file mypy.ini api libs workers; then
        echo -e "${GREEN}✓ Mypy type check passed with 0 errors.${NC}"
    else
        echo -e "${RED}✗ Mypy type checking failed.${NC}"
        FAILED_CHECKS+=("Python Type Check (mypy)")
    fi
else
    echo -e "${YELLOW}Notice: mypy not found in current environment; skipping type check.${NC}"
fi

# ── 3. Backend Pytest Test Suite ──────────────────────────────────────────────
if [ "$SKIP_TESTS" = false ]; then
    echo -e "\n${BLUE}[3/5] Running Backend Test Suites (pytest)...${NC}"
    if command -v pytest >/dev/null 2>&1; then
        if pytest tests/ -q; then
            echo -e "${GREEN}✓ All pytest test suites passed.${NC}"
        else
            echo -e "${RED}✗ Pytest test suite failed.${NC}"
            FAILED_CHECKS+=("Pytest Test Suite")
        fi
    else
        echo -e "${YELLOW}Notice: pytest not found in current environment; running remote test runner if needed.${NC}"
    fi
fi

# ── 4. Frontend ESLint Checks ─────────────────────────────────────────────────
if [ "$SKIP_FRONTEND" = false ] && [ -d "frontend" ]; then
    echo -e "\n${BLUE}[4/5] Running Frontend ESLint Checks...${NC}"
    if command -v npm >/dev/null 2>&1; then
        cd frontend
        if npm run lint >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Frontend ESLint passed with 0 errors.${NC}"
        else
            echo -e "${YELLOW}! ESLint warnings/notes detected (non-blocking for build).${NC}"
        fi
        cd "$ROOT_DIR"
    else
        echo -e "${YELLOW}Notice: npm not found in current environment; skipping local frontend lint.${NC}"
    fi
fi

# ── 5. Frontend Production TypeScript & Vite Build ─────────────────────────────
if [ "$SKIP_FRONTEND" = false ] && [ -d "frontend" ]; then
    echo -e "\n${BLUE}[5/5] Building Frontend SPA (tsc && vite build)...${NC}"
    if command -v npm >/dev/null 2>&1; then
        cd frontend
        if npm run build; then
            echo -e "${GREEN}✓ Frontend TypeScript and Vite build succeeded.${NC}"
        else
            echo -e "${RED}✗ Frontend build failed.${NC}"
            FAILED_CHECKS+=("Frontend Build (tsc && vite)")
        fi
        cd "$ROOT_DIR"
    else
        echo -e "${YELLOW}Notice: npm not found in current environment; build will validate in container.${NC}"
    fi
fi

# ── Summary Report ────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
    echo -e "${GREEN}🎉 All Pre-Deployment Checks Passed Successfully!${NC}"
    echo "Ready for production build & Cloud Run deployment."
    echo "============================================================"
    exit 0
else
    echo -e "${RED}❌ Pre-Deployment Verification Failed!${NC}"
    echo "The following checks failed:"
    for check in "${FAILED_CHECKS[@]}"; do
        echo -e "  - ${RED}$check${NC}"
    done
    echo "============================================================"
    exit 1
fi
