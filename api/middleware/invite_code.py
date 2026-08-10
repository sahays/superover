"""Invite code authentication middleware."""

import re
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that skip auth entirely
EXEMPT_PATHS = {"/health", "/api/auth/validate"}

# Path prefixes restricted to master users for ALL methods (read + write).
# Avatars expose a personal-data-rich live conversation; not suitable for
# anonymous invite-code holders.
MASTER_ONLY_PREFIXES = ("/api/avatars",)

# Write paths allowed for non-master users (exact match)
NON_MASTER_WRITE_ALLOWED = {"/api/auth/validate"}

# Write path prefixes allowed for non-master users
NON_MASTER_WRITE_PREFIXES = (
    "/api/scenes/signed-url",
    "/api/scenes/context/signed-url",
    "/api/media/jobs",
    "/api/images/jobs",
    "/api/engagement/signed-url",
    "/api/engagement/jobs",
    "/api/dubbing/jobs",
    "/api/dubbing/signed-url",
)

# Dynamic write paths allowed for non-master users
_SCENES_POST_EXACT = "/api/scenes"
_PROCESS_PATTERN = re.compile(r"^/api/scenes/[^/]+/process$")
_SEARCH_VIDEOS = re.compile(r"^/api/search/videos")


def _is_non_master_write_allowed(path: str, method: str) -> bool:
    """Check if a write request is allowed for non-master users."""
    if path in NON_MASTER_WRITE_ALLOWED:
        return True
    for prefix in NON_MASTER_WRITE_PREFIXES:
        if path.startswith(prefix):
            return True
    if method == "POST" and path == _SCENES_POST_EXACT:
        return True
    if method == "POST" and _PROCESS_PATTERN.match(path):
        return True
    if method == "POST" and _SEARCH_VIDEOS.match(path):
        return True
    return False


class InviteCodeMiddleware(BaseHTTPMiddleware):
    """Validates X-Invite-Code header on every request."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Allow exempt paths
        if path in EXEMPT_PATHS:
            request.state.is_master = False
            request.state.invite_code = ""
            request.state.owner = ""
            return await call_next(request)

        # Allow static assets and SPA routes (non-API)
        if not path.startswith("/api/") and path != "/health":
            request.state.is_master = False
            request.state.invite_code = ""
            request.state.owner = ""
            return await call_next(request)

        # Validate invite code
        code = request.headers.get("X-Invite-Code", "")
        if not code:
            return JSONResponse(status_code=401, content={"detail": "Invite code required"})

        from api.routes.auth import validate_code

        result = validate_code(code)
        if not result["valid"]:
            return JSONResponse(status_code=401, content={"detail": "Invalid invite code"})

        request.state.is_master = result["is_master"]
        request.state.is_admin = result.get("is_admin", False)
        request.state.invite_code = code
        request.state.owner = result.get("owner", "") or ""

        # Admins are treated as elevated for prefix and write checks. The
        # only master-only privilege left is creating new invite codes,
        # which is enforced inside the create_code route handler via
        # _require_master (admins reach the route but get 403 there).
        elevated = result["is_master"] or result.get("is_admin", False)

        # Block all access to master-only prefixes for non-elevated users
        if not elevated and any(path.startswith(p) for p in MASTER_ONLY_PREFIXES):
            return JSONResponse(
                status_code=403,
                content={"detail": "Master access required"},
            )

        # Block non-elevated write operations unless explicitly allowed
        if not elevated and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not _is_non_master_write_allowed(path, request.method):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Write access requires master or admin account"},
                )

        return await call_next(request)
