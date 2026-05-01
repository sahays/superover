"""API tests for the avatar feature.

Covers schema validation, master-only access control on the /api/avatars
prefix, CRUD round-trip, and the /live-config + /live-token endpoints.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app


MASTER = {"X-Invite-Code": "TEST-MASTER"}
GUEST = {"X-Invite-Code": "TEST-GUEST"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_master_auth():
    with patch("api.routes.auth.validate_code") as mock_validate:
        mock_validate.return_value = {"valid": True, "is_master": True}
        yield mock_validate


@pytest.fixture
def mock_guest_auth():
    with patch("api.routes.auth.validate_code") as mock_validate:
        mock_validate.return_value = {"valid": True, "is_master": False}
        yield mock_validate


@pytest.fixture
def mock_db():
    with patch("api.routes.avatars.get_db") as mock_get_db:
        db = MagicMock()
        mock_get_db.return_value = db
        yield db


def _avatar_record(**overrides) -> dict:
    base = {
        "id": "av-test123",
        "name": "Hana",
        "style": "to_the_point",
        "persona_prompt": "A test persona.",
        "voice": "Kore",
        "preset_name": "Hana",
        "language": "en-US",
        "default_greeting": "Hi.",
        "enable_grounding": False,
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------
# Schema validation
# ----------------------------------------------------------------------------


class TestCreateAvatarRequest:
    def test_requires_preset(self):
        from api.models.schemas.avatars import CreateAvatarRequest

        with pytest.raises(ValidationError):
            CreateAvatarRequest(name="x")

    def test_accepts_preset(self):
        from api.models.schemas.avatars import CreateAvatarRequest

        req = CreateAvatarRequest(name="x", preset_name="Hana")
        assert req.preset_name == "Hana"

    def test_rejects_unknown_voice(self):
        from api.models.schemas.avatars import CreateAvatarRequest

        with pytest.raises(ValidationError):
            CreateAvatarRequest.model_validate({"name": "x", "preset_name": "Hana", "voice": "NotAVoice"})

    def test_legacy_image_gcs_uri_field_is_ignored(self):
        """The field was dropped from the schema; sending it must not crash."""
        from api.models.schemas.avatars import CreateAvatarRequest

        req = CreateAvatarRequest.model_validate({"name": "x", "preset_name": "Hana", "image_gcs_uri": "gs://b/a.png"})
        assert req.preset_name == "Hana"
        assert not hasattr(req, "image_gcs_uri")


# ----------------------------------------------------------------------------
# build_system_instruction
# ----------------------------------------------------------------------------


class TestSystemInstruction:
    def test_includes_persona_and_style(self):
        from api.models.schemas.avatars import Avatar, AvatarStyle
        from libs.avatar_service import build_system_instruction

        avatar = Avatar(
            id="av-x",
            name="Hana",
            preset_name="Hana",
            style=AvatarStyle.funny,
            persona_prompt="Cricket commentator.",
        )
        sys_inst = build_system_instruction(avatar)
        assert "Hana" in sys_inst
        assert "Cricket commentator." in sys_inst
        assert "funny" in sys_inst.lower()

    def test_works_without_persona(self):
        from api.models.schemas.avatars import Avatar, AvatarStyle
        from libs.avatar_service import build_system_instruction

        avatar = Avatar(id="av-y", name="Bare", preset_name="Bare", style=AvatarStyle.serious)
        sys_inst = build_system_instruction(avatar)
        assert "Bare" in sys_inst
        assert "serious" in sys_inst.lower()
        assert "Persona note" not in sys_inst

    def test_default_mode_omits_search_overlay(self):
        from api.models.schemas.avatars import Avatar
        from libs.avatar_service import build_system_instruction

        avatar = Avatar(id="av-z", name="Hana", preset_name="Hana")
        sys_inst = build_system_instruction(avatar)
        assert "MODE: SEARCH ASSISTANT" not in sys_inst

    def test_search_mode_appends_overlay(self):
        from api.models.schemas.avatars import Avatar
        from libs.avatar_service import build_system_instruction

        avatar = Avatar(id="av-z", name="Hana", preset_name="Hana")
        sys_inst = build_system_instruction(avatar, mode="search")
        assert "MODE: SEARCH ASSISTANT" in sys_inst
        assert "search_movies" in sys_inst
        # Strict 3-step ordering must be present.
        assert "STEP 1" in sys_inst and "STEP 2" in sys_inst and "STEP 3" in sys_inst
        assert "Never invent" in sys_inst


# ----------------------------------------------------------------------------
# Setup-frame builder — search mode layers behaviour and overrides greeting.
# ----------------------------------------------------------------------------


class TestSetupFrame:
    def _avatar(self, **overrides):
        from api.models.schemas.avatars import Avatar

        base = dict(id="av-frame", name="Hana", preset_name="Hana", default_greeting="Hi! Talk cricket.")
        base.update(overrides)
        return Avatar(**base)

    def test_default_mode_uses_avatar_greeting(self, monkeypatch):
        from api.routes.avatars_live import _build_setup_frame
        from config import settings

        monkeypatch.setattr(settings, "avatar_live_project", "test-proj")
        frame = _build_setup_frame(self._avatar())
        text = frame["setup"]["systemInstruction"]["parts"][0]["text"]
        assert "Hi! Talk cricket." in text
        assert "MODE: SEARCH ASSISTANT" not in text

    def test_search_mode_drops_greeting(self, monkeypatch):
        """Search mode skips the greeting directive entirely — the desired
        flow is user-speaks → ack → tool-call → narrate, with the avatar
        silent until the user actually says something."""
        from api.routes.avatars_live import _build_setup_frame
        from config import settings

        monkeypatch.setattr(settings, "avatar_live_project", "test-proj")
        frame = _build_setup_frame(self._avatar(), "search")
        text = frame["setup"]["systemInstruction"]["parts"][0]["text"]
        # The avatar's own greeting must not leak in either.
        assert "Hi! Talk cricket." not in text
        # No "Open the conversation by saying exactly" directive at all.
        assert "Open the conversation" not in text
        # Search overlay still applies.
        assert "MODE: SEARCH ASSISTANT" in text

    def test_parse_mode_constrains_to_known_values(self):
        from api.routes.avatars_live import _parse_mode

        assert _parse_mode("search") == "search"
        assert _parse_mode("default") == "default"
        assert _parse_mode("anything-else") == "default"
        assert _parse_mode(None) == "default"

    def test_search_mode_declares_search_movies_tool(self, monkeypatch):
        from api.routes.avatars_live import _build_setup_frame
        from config import settings

        monkeypatch.setattr(settings, "avatar_live_project", "test-proj")
        frame = _build_setup_frame(self._avatar(), "search")
        tools = frame["setup"].get("tools", [])
        # Find the functionDeclarations block.
        decls = next((t for t in tools if "functionDeclarations" in t), None)
        assert decls is not None, "search mode must include functionDeclarations"
        names = [d["name"] for d in decls["functionDeclarations"]]
        assert "search_movies" in names
        # Schema sanity check.
        tool = next(d for d in decls["functionDeclarations"] if d["name"] == "search_movies")
        assert tool["parameters"]["required"] == ["query"]
        assert tool["parameters"]["properties"]["query"]["type"] == "string"

    def test_default_mode_omits_search_tool(self, monkeypatch):
        from api.routes.avatars_live import _build_setup_frame
        from config import settings

        monkeypatch.setattr(settings, "avatar_live_project", "test-proj")
        frame = _build_setup_frame(self._avatar(), "default")
        tools = frame["setup"].get("tools", [])
        for t in tools:
            if "functionDeclarations" in t:
                names = [d["name"] for d in t["functionDeclarations"]]
                assert "search_movies" not in names

    def test_search_tool_coexists_with_grounding(self, monkeypatch):
        from api.routes.avatars_live import _build_setup_frame
        from config import settings

        monkeypatch.setattr(settings, "avatar_live_project", "test-proj")
        avatar = self._avatar(enable_grounding=True)
        frame = _build_setup_frame(avatar, "search")
        tools = frame["setup"]["tools"]
        # Both tool blocks must be present, in either order.
        has_grounding = any("googleSearch" in t for t in tools)
        has_decls = any("functionDeclarations" in t for t in tools)
        assert has_grounding and has_decls


# ----------------------------------------------------------------------------
# Access control — middleware blocks guests on the master-only prefix.
# ----------------------------------------------------------------------------


class TestMasterOnlyGate:
    def test_guest_blocked_from_list(self, client, mock_guest_auth):
        res = client.get("/api/avatars", headers=GUEST)
        assert res.status_code == 403
        assert "Master access required" in res.json()["detail"]

    def test_guest_blocked_from_create(self, client, mock_guest_auth):
        res = client.post("/api/avatars", headers=GUEST, json={"name": "x", "preset_name": "Hana"})
        assert res.status_code == 403

    def test_guest_blocked_from_get(self, client, mock_guest_auth):
        res = client.get("/api/avatars/av-x", headers=GUEST)
        assert res.status_code == 403

    def test_guest_blocked_from_live_config(self, client, mock_guest_auth):
        res = client.get("/api/avatars/av-x/live-config", headers=GUEST)
        assert res.status_code == 403

    def test_guest_blocked_from_live_token(self, client, mock_guest_auth):
        res = client.post("/api/avatars/av-x/live-token", headers=GUEST)
        assert res.status_code == 403

    def test_missing_invite_code(self, client):
        res = client.get("/api/avatars")
        assert res.status_code == 401


# ----------------------------------------------------------------------------
# CRUD round-trip
# ----------------------------------------------------------------------------


class TestList:
    def test_returns_records(self, client, mock_master_auth, mock_db):
        mock_db.list_avatars.return_value = [_avatar_record(id="av-1", name="Hana")]
        res = client.get("/api/avatars", headers=MASTER)
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["id"] == "av-1"
        assert body[0]["name"] == "Hana"

    def test_drops_legacy_archived_field(self, client, mock_master_auth, mock_db):
        """Old Firestore docs may still have an archived flag — must not crash _serialize."""
        mock_db.list_avatars.return_value = [_avatar_record(archived=True)]
        res = client.get("/api/avatars", headers=MASTER)
        assert res.status_code == 200
        assert "archived" not in res.json()[0]


class TestGet:
    def test_returns_record(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = _avatar_record(id="av-9")
        res = client.get("/api/avatars/av-9", headers=MASTER)
        assert res.status_code == 200
        assert res.json()["id"] == "av-9"

    def test_404_when_missing(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = None
        res = client.get("/api/avatars/av-missing", headers=MASTER)
        assert res.status_code == 404


class TestCreate:
    def test_creates_preset_avatar(self, client, mock_master_auth, mock_db):
        mock_db.create_avatar.side_effect = lambda payload: payload
        res = client.post(
            "/api/avatars",
            headers=MASTER,
            json={"name": "Hana", "preset_name": "Hana", "voice": "Kore"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["name"] == "Hana"
        assert body["preset_name"] == "Hana"
        assert body["voice"] == "Kore"

    def test_create_rejects_when_no_preset(self, client, mock_master_auth, mock_db):
        res = client.post("/api/avatars", headers=MASTER, json={"name": "x"})
        assert res.status_code == 422


class TestUpdate:
    def test_patches_persona(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = _avatar_record(id="av-9")
        mock_db.update_avatar.return_value = _avatar_record(id="av-9", persona_prompt="New persona")
        res = client.patch(
            "/api/avatars/av-9",
            headers=MASTER,
            json={"persona_prompt": "  New persona  "},
        )
        assert res.status_code == 200
        assert res.json()["persona_prompt"] == "New persona"
        # Whitespace stripped before write.
        args, _ = mock_db.update_avatar.call_args
        assert args[1]["persona_prompt"] == "New persona"

    def test_rejects_empty_patch(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = _avatar_record(id="av-9")
        res = client.patch("/api/avatars/av-9", headers=MASTER, json={})
        assert res.status_code == 400

    def test_404_when_missing(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = None
        res = client.patch("/api/avatars/av-x", headers=MASTER, json={"name": "y"})
        assert res.status_code == 404


class TestDelete:
    def test_deletes(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = _avatar_record(id="av-9")
        res = client.delete("/api/avatars/av-9", headers=MASTER)
        assert res.status_code == 204
        mock_db.delete_avatar.assert_called_once_with("av-9")

    def test_404_when_missing(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = None
        res = client.delete("/api/avatars/av-missing", headers=MASTER)
        assert res.status_code == 404


# ----------------------------------------------------------------------------
# /live-config — exposes only non-secret fields.
# ----------------------------------------------------------------------------


class TestLiveConfig:
    def test_returns_payload(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = _avatar_record(name="Lumi", voice="Aoede")
        res = client.get("/api/avatars/av-test123/live-config", headers=MASTER)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["voice"] == "Aoede"
        assert body["language"] == "en-US"
        assert "Lumi" in body["system_instruction"]
        assert body["preset_name"] == "Hana"
        # Must not leak server-side config.
        assert "access_token" not in body
        assert "model" not in body
        assert "project" not in body

    def test_404_when_missing(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = None
        res = client.get("/api/avatars/av-x/live-config", headers=MASTER)
        assert res.status_code == 404


# ----------------------------------------------------------------------------
# /live-token — short-lived signed nonce for the WS upgrade.
# ----------------------------------------------------------------------------


class TestLiveToken:
    def test_mints_token(self, client, mock_master_auth, mock_db):
        from libs.avatar_token import verify_live_token

        mock_db.get_avatar.return_value = _avatar_record(id="av-tk")
        res = client.post("/api/avatars/av-tk/live-token", headers=MASTER)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["token"]
        assert verify_live_token(body["token"], "av-tk") is True

    def test_token_bound_to_avatar_id(self, client, mock_master_auth, mock_db):
        """A token minted for av-A must not validate for av-B."""
        from libs.avatar_token import verify_live_token

        mock_db.get_avatar.return_value = _avatar_record(id="av-A")
        res = client.post("/api/avatars/av-A/live-token", headers=MASTER)
        assert verify_live_token(res.json()["token"], "av-B") is False

    def test_404_when_missing(self, client, mock_master_auth, mock_db):
        mock_db.get_avatar.return_value = None
        res = client.post("/api/avatars/av-x/live-token", headers=MASTER)
        assert res.status_code == 404

    def test_verify_rejects_tampered_token(self):
        from libs.avatar_token import mint_live_token, verify_live_token

        token, _ = mint_live_token("av-x")
        # Flip the last hex char of the signature.
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert verify_live_token(tampered, "av-x") is False

    def test_verify_rejects_expired_token(self, monkeypatch):
        import libs.avatar_token as mod

        monkeypatch.setattr(mod, "_TTL_SECONDS", -1)
        token, _ = mod.mint_live_token("av-x")
        assert mod.verify_live_token(token, "av-x") is False

    def test_verify_rejects_garbage(self):
        from libs.avatar_token import verify_live_token

        for bad in ["", "not-a-token", "a.b.c", "a.notanint.c.d"]:
            assert verify_live_token(bad, "av-x") is False
