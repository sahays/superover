"""
Super Over Alchemy - Main API Application
FastAPI server for video analysis and scene recognition.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from api.routes import videos, tasks, media
from api.models.schemas import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("=" * 60)
    logger.info("Super Over Alchemy API Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"GCP Project: {settings.gcp_project_id}")
    logger.info(f"GCP Region: {settings.gcp_region}")
    logger.info(f"Uploads Bucket: {settings.uploads_bucket}")
    logger.info(f"Processed Bucket: {settings.processed_bucket}")
    logger.info(f"Results Bucket: {settings.results_bucket}")
    logger.info(f"Is Cloud Run: {settings.is_cloud_run()}")
    logger.info("=" * 60)

    # Ensure temp directory exists
    settings.get_temp_dir()

    yield

    # Shutdown
    logger.info("Super Over Alchemy API Shutting Down")


# Create FastAPI app
app = FastAPI(
    title="Super Over Alchemy API",
    description="Video analysis and scene recognition using Gemini AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(videos.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(media.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Super Over Alchemy API",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        environment=settings.environment,
        timestamp=datetime.utcnow()
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.is_local(),
        log_level="info"
    )
