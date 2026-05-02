"""Avatar feature schemas — interactive Gemini Live avatars (audio + video stream).

Only the v2 (Vertex Live) flow is modeled. Each avatar represents a persona
the user can drop into a real-time conversation; the actual session runs over
the WebSocket in `api/routes/avatars_live.py`.

Avatars use bundled Gemini Live preset portraits — see the PRESET_CATALOG on
the frontend. The preset name flows through to the Vertex Live setup frame as
`avatarConfig.avatarName`.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _new_id() -> str:
    return f"av-{uuid.uuid4().hex[:12]}"


class AvatarStyle(str, Enum):
    talkative = "talkative"
    funny = "funny"
    serious = "serious"
    cynical = "cynical"
    to_the_point = "to_the_point"


class AvatarVoice(str, Enum):
    """Prebuilt voices supported by Gemini Live.

    Names match the upstream gemini-avatar VOICE_PRESETS catalog. Gender
    grouping is the frontend's concern; the backend just validates the id.
    """

    Kore = "Kore"
    Puck = "Puck"
    Charon = "Charon"
    Fenrir = "Fenrir"
    Aoede = "Aoede"
    Leda = "Leda"
    Orus = "Orus"
    Zephyr = "Zephyr"
    Autonoe = "Autonoe"
    Umbriel = "Umbriel"
    Erinome = "Erinome"
    Laomedeia = "Laomedeia"
    Schedar = "Schedar"
    Achird = "Achird"
    Sadachbia = "Sadachbia"
    Enceladus = "Enceladus"
    Algieba = "Algieba"
    Algenib = "Algenib"
    Achernar = "Achernar"
    Gacrux = "Gacrux"
    Zubenelgenubi = "Zubenelgenubi"
    Sadaltager = "Sadaltager"
    Callirrhoe = "Callirrhoe"
    Iapetus = "Iapetus"
    Despina = "Despina"
    Rasalgethi = "Rasalgethi"
    Alnilam = "Alnilam"
    Pulcherrima = "Pulcherrima"
    Vindemiatrix = "Vindemiatrix"
    Sulafat = "Sulafat"


class Avatar(BaseModel):
    """Persisted avatar record — stored in Firestore as plain dicts."""

    id: str = Field(default_factory=_new_id)
    name: str
    style: AvatarStyle = AvatarStyle.to_the_point
    persona_prompt: str = ""
    # Free-form behavioural rules layered on top of the persona — language
    # matching, gendered grammar, formality, etc. Kept separate from
    # `persona_prompt` so "who they are" stays distinct from "how they
    # respond". Injected verbatim into the system instruction.
    behavior_instructions: str = ""
    voice: AvatarVoice = AvatarVoice.Kore
    # Maps to Gemini Live's avatarConfig.avatarName — required.
    preset_name: str
    # BCP-47 language code for ASR + TTS (e.g. "en-US", "es-ES", "ja-JP").
    language: str = "en-US"
    # First sentence the avatar speaks when the session opens. Empty = no
    # scripted opener — the model decides.
    default_greeting: str = ""
    # When true, the live session is configured with Google Search grounding.
    enable_grounding: bool = False
    created_at: Optional[datetime] = None


class CreateAvatarRequest(BaseModel):
    name: str
    style: AvatarStyle = AvatarStyle.to_the_point
    persona_prompt: str = ""
    behavior_instructions: str = ""
    voice: AvatarVoice = AvatarVoice.Kore
    preset_name: str
    language: str = "en-US"
    default_greeting: str = ""
    enable_grounding: bool = False


class UpdateAvatarRequest(BaseModel):
    name: Optional[str] = None
    style: Optional[AvatarStyle] = None
    persona_prompt: Optional[str] = None
    behavior_instructions: Optional[str] = None
    voice: Optional[AvatarVoice] = None
    language: Optional[str] = None
    default_greeting: Optional[str] = None
    enable_grounding: Optional[bool] = None


class AvatarResponse(BaseModel):
    id: str
    name: str
    style: AvatarStyle
    persona_prompt: str
    behavior_instructions: str = ""
    voice: AvatarVoice
    preset_name: str
    language: str
    default_greeting: str
    enable_grounding: bool
    created_at: Optional[datetime]


class LiveConfigResponse(BaseModel):
    """Non-secret config for the live UI.

    Model name, project, location, and access token stay server-side — the
    frontend just opens a WebSocket to /live, and the backend proxies the
    upstream Vertex AI Gemini Live connection.
    """

    voice: str
    language: str
    system_instruction: str
    preset_name: str
    default_greeting: str
    enable_grounding: bool


class LiveTokenResponse(BaseModel):
    """Short-lived signed token used to authorize a single /live WS upgrade.

    HTTP middleware doesn't run on WebSocket upgrades, so the frontend mints
    one of these via authenticated HTTP, then passes it on the WS query string.
    """

    token: str
    expires_at: datetime
