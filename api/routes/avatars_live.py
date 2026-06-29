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
from libs.avatar_service import (
    LiveMode,
    build_system_instruction,
)
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


def _build_system_instruction(avatar: Avatar, mode: LiveMode) -> str:
    """Thin wrapper around build_system_instruction. Kept as a hook in case
    we need mode-specific overlays later — currently it's a passthrough.
    """
    return build_system_instruction(avatar, mode=mode)


def _build_setup_frame(avatar: Avatar, mode: LiveMode = "default") -> dict:
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
        "systemInstruction": {"parts": [{"text": _build_system_instruction(avatar, mode)}]},
        "outputAudioTranscription": {},
        "inputAudioTranscription": {},
    }
    # NOTE: do not set `realtimeInputConfig.automaticActivityDetection` here.
    # It seemed like an obvious latency win (default ~1s end-of-turn detection)
    # but on this preview model the field destabilised the session: the model
    # stopped emitting `toolCall` frames entirely and produced silent audio.
    # The default VAD timing is what works.
    # Search mode used to declare a `search_movies` functionDeclaration here;
    # we now run a sequential pipeline on the frontend (ack → search → narrate)
    # so the model never calls a tool. Grounding (googleSearch) is the only
    # tool block that can appear, opt-in per avatar.
    if avatar.enable_grounding:
        setup["tools"] = [{"googleSearch": {}}]
    if not audio_only:
        setup["avatarConfig"] = {"avatarName": preset_name}
    return {"setup": setup}


def _parse_mode(raw: Optional[str]) -> LiveMode:
    """Constrain to known modes so a typo can't smuggle a free-text override
    into the system instruction."""
    return "search" if raw == "search" else "default"


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
            # logger.info — DEBUG is filtered by the INFO root logger in
            # api/main.py, so debug-level lines never reach Cloud Run. The
            # avatar_live_debug flag still gates these so they don't spam
            # in normal traffic.
            logger.info(f"[avatar:{avatar_id}] client→upstream first {tag}: {snippet}")


def _extract_client_text(payload: str) -> Optional[str]:
    """Pull the human-readable text out of a client `clientContent` turn frame,
    so each ack / small-talk / summary turn the frontend sends can be logged
    (with its timestamp) as it goes upstream. Returns None for non-turn frames
    (audio config, realtimeInput, etc.)."""
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    cc = data.get("clientContent") if isinstance(data, dict) else None
    if not isinstance(cc, dict):
        return None
    parts_text: list[str] = []
    for turn in cc.get("turns", []) or []:
        if isinstance(turn, dict):
            for part in turn.get("parts", []) or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts_text.append(part["text"])
    return " ".join(parts_text).strip() or None


def _try_extract_model_utterance(snippet: str) -> Optional[str]:
    """Pluck `serverContent.outputTranscription.text` from a JSON-shaped
    upstream frame. Returns None for non-JSON / non-transcript frames."""
    if "outputTranscription" not in snippet:
        return None
    try:
        msg = json.loads(snippet)
    except (ValueError, TypeError):
        return None
    text = msg.get("serverContent", {}).get("outputTranscription", {}).get("text")
    if isinstance(text, str) and text.strip():
        return text
    return None


def _log_first_model_utterance(avatar_id: str, snippet: str, first_utt_state: dict) -> None:
    """One-shot INFO log of the model's first spoken text. Independent of
    avatar_live_debug — always fires once per session so we can tell what
    the model is saying on connect even with debug off."""
    if first_utt_state.get("seen"):
        return
    text = _try_extract_model_utterance(snippet)
    if text:
        first_utt_state["seen"] = True
        logger.info(f"[avatar:{avatar_id}] first model utterance: {text!r}")


def _log_upstream_text(
    avatar_id: str, text_count: int, snippet: str, setup_complete_seen: bool, first_utt_state: dict
) -> bool:
    if settings.avatar_live_debug and text_count <= 10:
        logger.info(f"[avatar:{avatar_id}] upstream→client[txt#{text_count}]: {snippet}")
    if not setup_complete_seen and "setupComplete" in snippet:
        logger.info(f"[avatar:{avatar_id}] upstream: setupComplete received")
        setup_complete_seen = True
    _log_first_model_utterance(avatar_id, snippet, first_utt_state)
    if '"error"' in snippet or '"goAway"' in snippet:
        logger.warning(f"[avatar:{avatar_id}] upstream sent error/goAway: {snippet}")
    return setup_complete_seen


def _log_upstream_bytes(
    avatar_id: str, bytes_count: int, payload: bytes, setup_complete_seen: bool, first_utt_state: dict
) -> bool:
    if settings.avatar_live_debug and (bytes_count <= 5 or bytes_count % 25 == 0):
        logger.info(
            f"[avatar:{avatar_id}] upstream→client[bin#{bytes_count}] ({len(payload)} bytes): {_bin_preview(payload)}"
        )
    # Audio frames are large — skip them. Small frames may carry control
    # signals (setupComplete, turnComplete, error) we want to log every time,
    # so we no longer short-circuit once the first utterance is seen.
    if len(payload) >= 4096:
        return setup_complete_seen
    try:
        decoded = bytes(payload).decode("utf-8")
    except UnicodeDecodeError:
        return setup_complete_seen
    if not setup_complete_seen and "setupComplete" in decoded:
        logger.info(f"[avatar:{avatar_id}] upstream: setupComplete received (in binary frame)")
        setup_complete_seen = True
    _log_first_model_utterance(avatar_id, decoded, first_utt_state)
    if "turnComplete" in decoded:
        first_utt_state["turns"] = first_utt_state.get("turns", 0) + 1
        logger.info(f"[avatar:{avatar_id}] model turn-complete #{first_utt_state['turns']}")
    if '"error"' in decoded or '"goAway"' in decoded:
        logger.warning(f"[avatar:{avatar_id}] upstream sent error/goAway (binary): {decoded[:600]}")
    return setup_complete_seen


async def _relay_client_to_upstream(avatar_id: str, client_ws: WebSocket, upstream_ws) -> None:
    """Forward frames from the browser to Vertex AI verbatim."""
    forwarded = 0
    turns = 0
    sniffed: set[str] = set()
    tail = lambda: f"after {forwarded} frame(s), {turns} turn(s)"  # noqa: E731
    try:
        async for kind, payload in _iter_client_frames(client_ws):
            if kind == "text":
                _sniff_client_text(avatar_id, payload[:120], sniffed)
                # Always-on, low-volume: log each turn the frontend sends (ack /
                # small-talk / summary) with its timestamp, so the interaction
                # sequence is visible server-side without the debug flag.
                turn_text = _extract_client_text(payload)
                if turn_text is not None:
                    turns += 1
                    logger.info(f"[avatar:{avatar_id}] client→upstream turn#{turns}: {turn_text[:100]!r}")
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


async def _relay_upstream_to_client(
    avatar_id: str,
    client_ws: WebSocket,
    upstream_ws,
    kickstart_frame: Optional[str] = None,
) -> None:
    """Forward frames from Vertex AI to the browser verbatim.

    `kickstart_frame`, if provided, is sent upstream once we observe
    `setupComplete` — a deferred kickstart eliciting the configured greeting
    once the model is actually ready to act on it. Sending it before
    setupComplete is unreliable on this preview surface.
    """
    text_count = bytes_count = 0
    setup_complete_seen = False
    kickstart_sent = kickstart_frame is None
    first_utt_state: dict = {"seen": False}
    tail = lambda: (  # noqa: E731
        f"after {text_count + bytes_count} frame(s) (txt={text_count} bin={bytes_count})"
    )

    async def _maybe_send_kickstart() -> None:
        nonlocal kickstart_sent
        if kickstart_sent or not setup_complete_seen or kickstart_frame is None:
            return
        kickstart_sent = True
        await upstream_ws.send(kickstart_frame)
        logger.info(f"[avatar:{avatar_id}] sent deferred kickstart turn upstream (post-setupComplete)")

    try:
        async for kind, payload in _iter_upstream_frames(upstream_ws):
            if kind == "bytes":
                bytes_count += 1
                setup_complete_seen = _log_upstream_bytes(
                    avatar_id, bytes_count, payload, setup_complete_seen, first_utt_state
                )
                await _maybe_send_kickstart()
                await client_ws.send_bytes(payload)
            else:
                text_count += 1
                setup_complete_seen = _log_upstream_text(
                    avatar_id, text_count, payload[:600], setup_complete_seen, first_utt_state
                )
                await _maybe_send_kickstart()
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
    # logger.info because root logging is at INFO; avatar_live_debug already
    # gates this so it doesn't fire in normal traffic.
    logger.info(f"[avatar:{avatar_id}] setup frame: {setup_frame[:1500]}")


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


async def _run_relay(avatar_id: str, ws: WebSocket, upstream_ws, kickstart_frame: Optional[str] = None) -> None:
    """Race the two relay directions; whichever finishes first cancels the other."""
    relay_a = asyncio.create_task(_relay_client_to_upstream(avatar_id, ws, upstream_ws))
    relay_b = asyncio.create_task(
        _relay_upstream_to_client(avatar_id, ws, upstream_ws, kickstart_frame=kickstart_frame)
    )
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
    mode = _parse_mode(ws.query_params.get("mode"))
    logger.info(f"[avatar:{avatar_id}] live ws upgrade requested (mode={mode})")

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
        setup_frame = json.dumps(_build_setup_frame(avatar, mode))
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
        # Kickstart only in default (avatar-page) mode so the avatar greets
        # the user on connect. In search mode the desired flow is
        # user-speaks → ack → search → narrate with no opening utterance,
        # so we skip the kickstart entirely and the model stays silent
        # until the user clicks Speak and talks.
        kickstart_frame: Optional[str] = None
        if mode != "search":
            kickstart_frame = json.dumps(
                {
                    "clientContent": {
                        "turns": [{"role": "user", "parts": [{"text": "Hi"}]}],
                        "turnComplete": True,
                    }
                }
            )
        await ws.accept()
        logger.info(f"[avatar:{avatar_id}] client WS accepted; starting relay (mode={mode})")
        await _run_relay(avatar_id, ws, upstream_ws, kickstart_frame=kickstart_frame)
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
