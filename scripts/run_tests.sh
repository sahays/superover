#!/bin/bash
# Test runner script for Super Over Alchemy

set -e

echo "==================================="
echo "Super Over Alchemy - Test Runner"
echo "==================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade test dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements-test.txt

# Parse arguments
TEST_TYPE=${1:-all}
COVERAGE=${2:-false}

echo ""
echo "Test Type: $TEST_TYPE"
echo "Coverage: $COVERAGE"
echo ""

# Run tests based on type
case $TEST_TYPE in
    api)
        echo -e "${YELLOW}Running API tests...${NC}"
        if [ "$COVERAGE" = "true" ]; then
            pytest tests/api/ -v --cov=api --cov-report=html --cov-report=term
        else
            pytest tests/api/ -v
        fi
        ;;
    worker)
        echo -e "${YELLOW}Running worker tests...${NC}"
        if [ "$COVERAGE" = "true" ]; then
            pytest tests/workers/ -v --cov=workers --cov-report=html --cov-report=term
        else
            pytest tests/workers/ -v
        fi
        ;;
    libs)
        echo -e "${YELLOW}Running library tests...${NC}"
        if [ "$COVERAGE" = "true" ]; then
            pytest tests/libs/ -v --cov=libs --cov-report=html --cov-report=term
        else
            pytest tests/libs/ -v
        fi
        ;;
    unit)
        echo -e "${YELLOW}Running unit tests...${NC}"
        if [ "$COVERAGE" = "true" ]; then
            pytest -m unit -v --cov --cov-report=html --cov-report=term
        else
            pytest -m unit -v
        fi
        ;;
    integration)
        echo -e "${YELLOW}Running integration tests...${NC}"
        if [ "$COVERAGE" = "true" ]; then
            pytest -m integration -v --cov --cov-report=html --cov-report=term
        else
            pytest -m integration -v
        fi
        ;;
    all)
        echo -e "${YELLOW}Running all tests...${NC}"
        if [ "$COVERAGE" = "true" ]; then
            pytest tests/ -v --cov --cov-report=html --cov-report=term
        else
            pytest tests/ -v
        fi
        ;;
    *)
        echo -e "${RED}Invalid test type: $TEST_TYPE${NC}"
        echo "Valid options: api, worker, libs, unit, integration, all"
        exit 1
        ;;
esac

# Check test result
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    if [ "$COVERAGE" = "true" ]; then
        echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
    fi
else
    echo ""
    echo -e "${RED}✗ Tests failed${NC}"
    exit 1
fi
