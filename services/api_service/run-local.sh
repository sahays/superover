#!/bin/bash

# Run API Service Locally
# This script runs the FastAPI service on localhost:8000

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Starting Super Over Alchemy API Service locally...${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Note: Environment variables are loaded by python-dotenv from ../../.env
# We only need to override FRONTEND_URL for local development
export FRONTEND_URL="http://localhost:3000"
echo -e "${BLUE}Using FRONTEND_URL: $FRONTEND_URL${NC}"

echo -e "${GREEN}Starting API service on http://localhost:8000${NC}"
echo -e "${BLUE}API docs available at http://localhost:8000/docs${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"

# Run the service
cd ../..
uvicorn services.api_service.main:app --reload --host 0.0.0.0 --port 8000
