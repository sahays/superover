"""Scene management API routes — assembled from sub-modules."""

from fastapi import APIRouter

from .uploads import register_upload_routes
from .jobs import register_job_routes
from .videos import register_video_routes
from .results import register_result_routes

router = APIRouter(prefix="/scenes", tags=["scenes"])

# Registration order matters: static paths (/signed-url, /jobs) before parameterized (/{video_id})
register_upload_routes(router)
register_job_routes(router)
register_video_routes(router)
register_result_routes(router)
