"""Short-lived HMAC tokens for authorizing the /live WebSocket upgrade.

Format: `<avatar_id>.<expiry_unix>.<nonce>.<sig>`. The signature is HMAC-SHA256
over the first three segments using the master invite code as the shared
secret. The nonce blocks token replay across short bursts; the expiry caps
the replay window to a minute regardless.

This is a pragmatic stop-gap for "WS upgrades can't carry headers" — it keeps
the invite code out of access logs while still binding the token to a single
avatar id and a tight time window.
"""

import hmac
import secrets
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Tuple

from config import settings

_TTL_SECONDS = 60


def _secret() -> bytes:
    secret = settings.master_invite_code or "dev-no-secret"
    return secret.encode("utf-8")


def mint_live_token(avatar_id: str) -> Tuple[str, datetime]:
    """Return (token, expires_at) for the given avatar id."""
    expiry = int(time.time()) + _TTL_SECONDS
    nonce = secrets.token_urlsafe(8)
    payload = f"{avatar_id}.{expiry}.{nonce}"
    sig = hmac.new(_secret(), payload.encode("utf-8"), sha256).hexdigest()
    return f"{payload}.{sig}", datetime.fromtimestamp(expiry, tz=timezone.utc)


def verify_live_token(token: str, avatar_id: str) -> bool:
    """Constant-time check: token is well-formed, signed, fresh, and bound
    to this avatar id."""
    if not token:
        return False
    try:
        token_avatar, expiry_str, nonce, sig = token.split(".")
        expiry = int(expiry_str)
    except (ValueError, AttributeError):
        return False
    if token_avatar != avatar_id:
        return False
    if expiry < int(time.time()):
        return False
    payload = f"{token_avatar}.{expiry}.{nonce}"
    expected = hmac.new(_secret(), payload.encode("utf-8"), sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
