"""
Super Over Alchemy - Main API Application
FastAPI server for video analysis and scene recognition.
Serves the Vite SPA in production (same-origin, no CORS needed).
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from config import settings
from api.routes import scenes, media, prompts, images, search, branding
from api.models.schemas import HealthResponse

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Resolve frontend dist directory (built by Vite)
FRONTEND_DIST = project_root / "frontend" / "dist"


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
    logger.info(f"Frontend dist: {FRONTEND_DIST} (exists={FRONTEND_DIST.exists()})")
    logger.info("=" * 60)

    # Ensure temp directory exists
    settings.get_temp_dir()

    yield

    # Shutdown
    logger.info("Super Over Alchemy API Shutting Down")


# Create FastAPI app
app = FastAPI(
    title="Super Over Alchemy API",
    description="Scene analysis and recognition using Gemini AI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — only needed for local dev (Vite on :3000 → API on :8000).
# In production the SPA is served same-origin, so no CORS required.
if settings.is_local():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc: HTTPException):
    """Return structured JSON for rate limit errors."""
    return JSONResponse(
        status_code=429,
        content={"detail": exc.detail},
        headers={"Retry-After": str(exc.detail.get("retry_after", 600))},
    )


# Include routers
app.include_router(scenes.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(branding.router, prefix="/api")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="healthy", environment=settings.environment, timestamp=datetime.utcnow())


# --- SPA static file serving ---
# Mount Vite's assets directory (JS/CSS bundles with content hashes)
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static-assets")


@app.get("/{path:path}")
async def serve_spa(request: Request, path: str):
    """
    Catch-all: serve the SPA's index.html for client-side routing.
    API and health paths are matched by their own routes first; this guard
    catches any unmatched /api/* or /health sub-paths that would otherwise
    silently return index.html.
    """
    if path.startswith("api/") or path == "health":
        raise HTTPException(status_code=404, detail="Not found")

    # Try to serve a static file from dist/ first
    if FRONTEND_DIST.exists():
        file_path = FRONTEND_DIST / path
        if file_path.is_file():
            return FileResponse(str(file_path))

        # Fall back to index.html for SPA routing
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))

    # No frontend build available — return API info
    return {
        "service": "Super Over Alchemy API",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment,
        "note": "Frontend not built. Run 'cd frontend && npm run build' first.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.is_local(),
        log_level="info",
    )
