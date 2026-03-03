"""Firestore-based rate limiting for FastAPI endpoints."""

from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from libs.database import get_db


def rate_limit(endpoint_group: str, max_requests: int = 2, window_minutes: int = 10):
    """Return a FastAPI dependency that enforces rate limits via Firestore.

    Usage:
        @router.post("/endpoint", dependencies=[Depends(rate_limit("group_name"))])
        async def endpoint(request: Request): ...
    """

    async def _check(request: Request):
        client_ip = _get_client_ip(request)
        db = get_db()
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

        # Query recent requests for this IP + endpoint group
        docs = (
            db.client.collection("rate_limits")
            .where("client_ip", "==", client_ip)
            .where("endpoint_group", "==", endpoint_group)
            .where("timestamp", ">=", cutoff)
            .stream()
        )
        count = sum(1 for _ in docs)

        if count >= max_requests:
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": (f"Rate limit exceeded. Maximum {max_requests} requests per {window_minutes} minutes."),
                    "retry_after": window_minutes * 60,
                },
            )

        # Record this request
        db.client.collection("rate_limits").add(
            {
                "client_ip": client_ip,
                "endpoint_group": endpoint_group,
                "timestamp": datetime.utcnow(),
                "ttl": datetime.utcnow() + timedelta(minutes=window_minutes),
            }
        )

    return _check


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For from Cloud Run load balancer."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
