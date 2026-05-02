"""Tests for the invite-code admin role.

Admin grants master-level access everywhere except creating new invite
codes (which would let admins escalate privileges). The env-var master
code stays its own role and is never marked admin.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


MASTER = {"X-Invite-Code": "TEST-MASTER"}
ADMIN = {"X-Invite-Code": "TEST-ADMIN"}
GUEST = {"X-Invite-Code": "TEST-GUEST"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_master_auth():
    with patch("api.routes.auth.validate_code") as v:
        v.return_value = {"valid": True, "is_master": True, "is_admin": False}
        yield v


@pytest.fixture
def mock_admin_auth():
    with patch("api.routes.auth.validate_code") as v:
        v.return_value = {"valid": True, "is_master": False, "is_admin": True}
        yield v


@pytest.fixture
def mock_guest_auth():
    with patch("api.routes.auth.validate_code") as v:
        v.return_value = {"valid": True, "is_master": False, "is_admin": False}
        yield v


@pytest.fixture
def mock_db():
    with patch("api.routes.auth.get_db") as g:
        db = MagicMock()
        g.return_value = db
        yield db


# ----------------------------------------------------------------------------
# validate_code shape — the contract the middleware and frontend rely on.
# ----------------------------------------------------------------------------


class TestValidateCodeShape:
    def test_master_envvar_returns_master_not_admin(self, monkeypatch):
        from config import settings
        from api.routes.auth import validate_code

        monkeypatch.setattr(settings, "master_invite_code", "MAGIC-MASTER")
        result = validate_code("MAGIC-MASTER")
        assert result == {"valid": True, "is_master": True, "is_admin": False}

    def test_stored_admin_code_returns_admin(self, monkeypatch):
        from config import settings
        from api.routes.auth import validate_code

        monkeypatch.setattr(settings, "master_invite_code", "")
        with patch("api.routes.auth.get_db") as g:
            db = MagicMock()
            db.get_invite_code_by_value.return_value = {
                "id": "x",
                "code": "ADM",
                "is_active": True,
                "is_admin": True,
            }
            g.return_value = db
            result = validate_code("ADM")
        assert result == {"valid": True, "is_master": False, "is_admin": True}

    def test_stored_regular_code_returns_neither(self, monkeypatch):
        from config import settings
        from api.routes.auth import validate_code

        monkeypatch.setattr(settings, "master_invite_code", "")
        with patch("api.routes.auth.get_db") as g:
            db = MagicMock()
            db.get_invite_code_by_value.return_value = {
                "id": "x",
                "code": "USR",
                "is_active": True,
            }
            g.return_value = db
            result = validate_code("USR")
        assert result == {"valid": True, "is_master": False, "is_admin": False}

    def test_unknown_code_invalid(self, monkeypatch):
        from config import settings
        from api.routes.auth import validate_code

        monkeypatch.setattr(settings, "master_invite_code", "")
        with patch("api.routes.auth.get_db") as g:
            db = MagicMock()
            db.get_invite_code_by_value.return_value = None
            g.return_value = db
            result = validate_code("WHO?")
        assert result == {"valid": False, "is_master": False, "is_admin": False}


# ----------------------------------------------------------------------------
# Middleware — admin passes the same gates as master.
# ----------------------------------------------------------------------------


class TestAdminMiddleware:
    def test_admin_passes_master_only_prefix(self, client, mock_admin_auth):
        """GET /api/avatars is in MASTER_ONLY_PREFIXES — admin must be allowed."""
        with patch("api.routes.avatars.get_db") as g:
            db = MagicMock()
            db.list_avatars.return_value = []
            g.return_value = db
            res = client.get("/api/avatars", headers=ADMIN)
        assert res.status_code == 200

    def test_guest_blocked_from_master_only_prefix(self, client, mock_guest_auth):
        res = client.get("/api/avatars", headers=GUEST)
        assert res.status_code == 403


# ----------------------------------------------------------------------------
# Auth routes — admin can manage codes EXCEPT create.
# ----------------------------------------------------------------------------


class TestAdminAuthRoutes:
    def test_admin_can_list_codes(self, client, mock_admin_auth, mock_db):
        mock_db.get_invite_codes.return_value = []
        res = client.get("/api/auth/codes", headers=ADMIN)
        assert res.status_code == 200

    def test_admin_blocked_from_create(self, client, mock_admin_auth, mock_db):
        res = client.post(
            "/api/auth/codes",
            headers=ADMIN,
            json={"code": "NEW-CODE", "label": ""},
        )
        assert res.status_code == 403
        assert "Master access required" in res.json()["detail"]

    def test_master_can_create_admin_code(self, client, mock_master_auth, mock_db):
        mock_db.get_invite_code_by_value.return_value = None
        mock_db.create_invite_code.return_value = {
            "id": "abc",
            "code": "ADM",
            "label": "moderator",
            "is_active": True,
            "is_admin": True,
            "expires_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        res = client.post(
            "/api/auth/codes",
            headers=MASTER,
            json={"code": "ADM", "label": "moderator", "is_admin": True},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["is_admin"] is True
        # Verify the DB call carried the flag.
        kwargs = mock_db.create_invite_code.call_args.kwargs
        assert kwargs["is_admin"] is True

    def test_admin_blocked_from_revoke(self, client, mock_admin_auth, mock_db):
        """Revoke is master-only — admins must not be able to deactivate
        another user's invite code."""
        res = client.post("/api/auth/codes/abc/revoke", headers=ADMIN)
        assert res.status_code == 403
        mock_db.update_invite_code.assert_not_called()

    def test_admin_blocked_from_activate(self, client, mock_admin_auth, mock_db):
        """Activate is the inverse of revoke — also master-only."""
        res = client.post("/api/auth/codes/abc/activate", headers=ADMIN)
        assert res.status_code == 403
        mock_db.update_invite_code.assert_not_called()

    def test_admin_blocked_from_delete(self, client, mock_admin_auth, mock_db):
        """Delete is master-only — admins must not be able to remove other
        users' invite codes."""
        res = client.delete("/api/auth/codes/abc", headers=ADMIN)
        assert res.status_code == 403
        mock_db.delete_invite_code.assert_not_called()

    def test_admin_can_patch_label(self, client, mock_admin_auth, mock_db):
        mock_db.update_invite_code.return_value = {
            "id": "abc",
            "code": "X",
            "is_active": True,
            "is_admin": False,
            "label": "renamed",
        }
        res = client.patch("/api/auth/codes/abc", headers=ADMIN, json={"label": "renamed"})
        assert res.status_code == 200

    def test_guest_blocked_from_list(self, client, mock_guest_auth):
        # Listing was previously implicitly master-only via middleware; now
        # _require_elevated handles it. Guest still 403s.
        res = client.get("/api/auth/codes", headers=GUEST)
        assert res.status_code == 403
