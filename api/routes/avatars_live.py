"""Avatar live session — WebSocket proxy to Vertex Gemini Live.

Browser ⟷ this backend ⟷ Vertex AI Bidi WS. Tokens never leave the backend;
the frontend opens a WS to /api/avatars/{id}/live and the relay forwards
frames in both directions verbatim.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.models.schemas.avatars import Avatar
from config import settings
from libs.avatar_service import build_system_instruction
from libs.avatar_token import verify_live_token
from libs.database import get_db
from libs.gcp_auth import vertex_access_token

# Default global-region host for the Gemini Live preview (autopush sandbox).
# Override via settings.avatar_live_host_override when the model graduates.
_DEFAULT_GLOBAL_HOST = "autopush-aiplatform.sandbox.googleapis.com"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/avatars", tags=["avatars"])


def _live_host(location: str) -> str:
    if settings.avatar_live_host_override:
        return settings.avatar_live_host_override
    if location == "global":
        return _DEFAULT_GLOBAL_HOST
    return f"{location}-aiplatform.googleapis.com"


def _avatar_or_none(avatar_id: str) -> Optional[Avatar]:
    record = get_db().get_avatar(avatar_id)
    if not record:
        return None
    return Avatar(**{k: v for k, v in record.items() if k in Avatar.model_fields})


# ---------------------------------------------------------------------------
# Setup-frame builders
# ---------------------------------------------------------------------------


def _build_speech_config(avatar: Avatar) -> dict:
    voice_name = avatar.voice.value.lower()
    return {
        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}},
        "languageCode": avatar.language or "en-US",
    }


def _build_system_instruction(avatar: Avatar) -> str:
    """Wedge the default greeting into the system prompt so the model speaks
    it on connect — Gemini Live has no separate `default_greeting` slot."""
    text = build_system_instruction(avatar)
    if avatar.default_greeting:
        text += f'\n\nOpen the conversation by saying exactly: "{avatar.default_greeting.strip()}"'
    return text


def _build_setup_frame(avatar: Avatar) -> dict:
    """First frame on the upstream WS — model, voice, system instruction,
    modalities. Built server-side so the browser can't tamper with them."""
    project = settings.avatar_live_project
    location = settings.avatar_live_location
    model = settings.avatar_live_model
    model_path = f"projects/{project}/locations/{location}/publishers/google/models/{model}"
    audio_only = settings.avatar_live_audio_only
    preset_name = avatar.preset_name or settings.avatar_live_preset_name

    setup: dict = {
        "model": model_path,
        "generationConfig": {
            "responseModalities": ["AUDIO"] if audio_only else ["VIDEO"],
            "speechConfig": _build_speech_config(avatar),
        },
        "systemInstruction": {"parts": [{"text": _build_system_instruction(avatar)}]},
        "outputAudioTranscription": {},
        "inputAudioTranscription": {},
    }
    if avatar.enable_grounding:
        setup["tools"] = [{"googleSearch": {}}]
    if not audio_only:
        setup["avatarConfig"] = {"avatarName": preset_name}
    return {"setup": setup}


# ---------------------------------------------------------------------------
# WebSocket relay
# ---------------------------------------------------------------------------

CLIENT_SNIFF_TAGS = (
    "realtimeInput",
    "clientContent",
    "audio/pcm",
    "audio/webm",
    "video/",
)


async def _iter_client_frames(client_ws: WebSocket):
    """Yield ('text'|'bytes', payload) from the browser-side WebSocket until
    a disconnect arrives."""
    while True:
        msg = await client_ws.receive()
        if msg.get("type") == "websocket.disconnect":
            return
        text = msg.get("text")
        if text is not None:
            yield "text", text
            continue
        data = msg.get("bytes")
        if data is not None:
            yield "bytes", data


async def _iter_upstream_frames(upstream_ws):
    """Yield ('text'|'bytes', payload) from the Vertex AI WebSocket."""
    async for msg in upstream_ws:
        if isinstance(msg, (bytes, bytearray)):
            yield "bytes", bytes(msg)
        else:
            yield "text", msg


def _bin_preview(payload: bytes) -> str:
    try:
        return bytes(payload[:600]).decode("utf-8")
    except UnicodeDecodeError:
        return "hex:" + bytes(payload[:80]).hex()


def _sniff_client_text(avatar_id: str, snippet: str, sniffed: set[str]) -> None:
    if not settings.avatar_live_debug:
        return
    for tag in CLIENT_SNIFF_TAGS:
        if tag in snippet and tag not in sniffed:
            sniffed.add(tag)
            logger.debug(f"[avatar:{avatar_id}] client→upstream first {tag}: {snippet}")


def _log_upstream_text(avatar_id: str, text_count: int, snippet: str, setup_complete_seen: bool) -> bool:
    if settings.avatar_live_debug and text_count <= 10:
        logger.debug(f"[avatar:{avatar_id}] upstream→client[txt#{text_count}]: {snippet}")
    if not setup_complete_seen and "setupComplete" in snippet:
        logger.info(f"[avatar:{avatar_id}] upstream: setupComplete received")
        setup_complete_seen = True
    if '"error"' in snippet or '"goAway"' in snippet:
        logger.warning(f"[avatar:{avatar_id}] upstream sent error/goAway: {snippet}")
    return setup_complete_seen


def _log_upstream_bytes(avatar_id: str, bytes_count: int, payload: bytes, setup_complete_seen: bool) -> bool:
    if settings.avatar_live_debug and (bytes_count <= 5 or bytes_count % 25 == 0):
        logger.debug(
            f"[avatar:{avatar_id}] upstream→client[bin#{bytes_count}] ({len(payload)} bytes): {_bin_preview(payload)}"
        )
    if setup_complete_seen or len(payload) >= 4096:
        return setup_complete_seen
    try:
        decoded = bytes(payload).decode("utf-8")
    except UnicodeDecodeError:
        return setup_complete_seen
    if "setupComplete" in decoded:
        logger.info(f"[avatar:{avatar_id}] upstream: setupComplete received (in binary frame)")
        return True
    if '"error"' in decoded or '"goAway"' in decoded:
        logger.warning(f"[avatar:{avatar_id}] upstream sent error/goAway (binary): {decoded[:600]}")
    return setup_complete_seen


async def _relay_client_to_upstream(avatar_id: str, client_ws: WebSocket, upstream_ws) -> None:
    """Forward frames from the browser to Vertex AI verbatim."""
    forwarded = 0
    sniffed: set[str] = set()
    tail = lambda: f"after {forwarded} frame(s) kinds={sorted(sniffed)}"  # noqa: E731
    try:
        async for kind, payload in _iter_client_frames(client_ws):
            if kind == "text":
                _sniff_client_text(avatar_id, payload[:120], sniffed)
            await upstream_ws.send(payload)
            forwarded += 1
        logger.info(f"[avatar:{avatar_id}] client→upstream: client disconnected {tail()}")
    except asyncio.CancelledError:
        logger.info(f"[avatar:{avatar_id}] client→upstream: cancelled {tail()}")
        raise
    except WebSocketDisconnect:
        logger.info(f"[avatar:{avatar_id}] client→upstream: WebSocketDisconnect {tail()}")
        return
    except Exception as e:
        logger.exception(f"[avatar:{avatar_id}] client→upstream: unexpected error {tail()}: {e}")
        raise


async def _relay_upstream_to_client(avatar_id: str, client_ws: WebSocket, upstream_ws) -> None:
    """Forward frames from Vertex AI to the browser verbatim."""
    text_count = bytes_count = 0
    setup_complete_seen = False
    tail = lambda: (  # noqa: E731
        f"after {text_count + bytes_count} frame(s) (txt={text_count} bin={bytes_count})"
    )
    try:
        async for kind, payload in _iter_upstream_frames(upstream_ws):
            if kind == "bytes":
                bytes_count += 1
                setup_complete_seen = _log_upstream_bytes(avatar_id, bytes_count, payload, setup_complete_seen)
                await client_ws.send_bytes(payload)
            else:
                text_count += 1
                setup_complete_seen = _log_upstream_text(avatar_id, text_count, payload[:600], setup_complete_seen)
                await client_ws.send_text(payload)
        logger.info(f"[avatar:{avatar_id}] upstream→client: stream ended {tail()}")
    except asyncio.CancelledError:
        logger.info(f"[avatar:{avatar_id}] upstream→client: cancelled {tail()}")
        raise
    except Exception as e:
        cls = type(e).__name__
        msg = str(e) or repr(e)
        level = logger.info if "ConnectionClosed" in cls else logger.warning
        level(
            f"[avatar:{avatar_id}] upstream→client: "
            f"{'closed by upstream' if 'ConnectionClosed' in cls else 'error'} "
            f"{tail()} ({cls}: {msg})"
        )
        raise


# ---------------------------------------------------------------------------
# /live WebSocket
# ---------------------------------------------------------------------------


def _log_setup_frame(avatar_id: str, setup_frame: str) -> None:
    if not settings.avatar_live_debug:
        return
    try:
        logger.debug(f"[avatar:{avatar_id}] setup frame: {setup_frame[:1500]}")
    except Exception:
        pass


async def _open_upstream(avatar_id: str, token: str):
    """Open the Vertex AI Live WS. Token rides in the Authorization header
    (not the URL) so it doesn't end up in access logs. The `x-goog-user-project`
    header tells GCP which project to bill / quota-check against — without it
    the autopush API looks at the access token's owning project, which isn't
    allowlisted."""
    location = settings.avatar_live_location
    host = _live_host(location)
    live_project = settings.avatar_live_project
    model = settings.avatar_live_model
    url = f"wss://{host}/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
    logger.info(
        f"[avatar:{avatar_id}] live session: project={live_project} location={location} host={host} model={model}"
    )
    logger.info(f"[avatar:{avatar_id}] connecting upstream WS to {url}")
    import websockets

    return await websockets.connect(
        url,
        max_size=None,
        additional_headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": live_project,
        },
    )


async def _run_relay(avatar_id: str, ws: WebSocket, upstream_ws) -> None:
    """Race the two relay directions; whichever finishes first cancels the other."""
    relay_a = asyncio.create_task(_relay_client_to_upstream(avatar_id, ws, upstream_ws))
    relay_b = asyncio.create_task(_relay_upstream_to_client(avatar_id, ws, upstream_ws))
    done, pending = await asyncio.wait({relay_a, relay_b}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        exc = t.exception()
        if exc:
            logger.warning(f"[avatar:{avatar_id}] relay task ended with {type(exc).__name__}: {exc}")


@router.websocket("/{avatar_id}/live")
async def avatar_live(ws: WebSocket, avatar_id: str):
    """Proxy WebSocket: browser <-> backend <-> Vertex AI Gemini Live.

    The backend mints a service-account access token per session and opens
    the upstream WS using it. Tokens never leave the backend.

    Auth: client must present a short-lived signed token from
    POST /api/avatars/{id}/live-token in the `?token=` query string.
    """
    logger.info(f"[avatar:{avatar_id}] live ws upgrade requested")

    if not verify_live_token(ws.query_params.get("token", ""), avatar_id):
        logger.warning(f"[avatar:{avatar_id}] live ws rejected: invalid/expired live token")
        await ws.close(code=4401)
        return

    avatar = _avatar_or_none(avatar_id)
    if not avatar:
        logger.warning(f"[avatar:{avatar_id}] live ws rejected: avatar not found")
        await ws.close(code=4404)
        return

    if not settings.avatar_live_project:
        logger.error(f"[avatar:{avatar_id}] live ws rejected: avatar_live_project not configured")
        await ws.close(code=1011, reason="avatar_live_project not configured")
        return

    try:
        token = vertex_access_token()
    except Exception as e:
        logger.exception(f"[avatar:{avatar_id}] token mint failed: {e}")
        await ws.close(code=1011)
        return

    try:
        setup_frame = json.dumps(_build_setup_frame(avatar))
    except Exception as e:
        logger.exception(f"[avatar:{avatar_id}] setup frame build failed: {e}")
        await ws.close(code=1011)
        return
    _log_setup_frame(avatar_id, setup_frame)

    try:
        upstream_ws = await _open_upstream(avatar_id, token)
    except Exception as e:
        logger.exception(f"[avatar:{avatar_id}] upstream connect failed: {type(e).__name__}: {e}")
        await ws.close(code=1011)
        return
    logger.info(f"[avatar:{avatar_id}] upstream WS connected")

    try:
        await upstream_ws.send(setup_frame)
        await ws.accept()
        logger.info(f"[avatar:{avatar_id}] client WS accepted; starting relay")
        await _run_relay(avatar_id, ws, upstream_ws)
    except Exception as e:
        logger.exception(f"[avatar:{avatar_id}] live relay error: {e}")
    finally:
        try:
            await upstream_ws.close()
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass
