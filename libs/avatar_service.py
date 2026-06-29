"""Avatar service — system-instruction builder for Gemini Live sessions."""

from typing import Literal

from api.models.schemas.avatars import Avatar, AvatarStyle

LiveMode = Literal["default", "search"]

# Layered onto the avatar's normal system instruction when mode=search.
# The frontend orchestrates a sequential pipeline: the user clicks stop,
# the panel sends a "Briefly acknowledge the request" prompt, the search
# runs in parallel, and once both the search returns and the avatar's ack
# audio finishes, the panel injects a `[SEARCH_RESULTS] …` message for
# the model to narrate. This overlay just teaches the model the two
# response shapes — there's no tool, no [SEARCH_RESULTS] auto-detection
# logic in the model itself; the frontend cues each phase.
SEARCH_MODE_OVERLAY = (
    "\n\nMODE: SEARCH ASSISTANT\n"
    "You help the user find movies and clips from a curated library. The "
    "search runs separately and takes several seconds; you don't know what's "
    "in the library until the system tells you. Stay fully in your own voice "
    "and personality (above) through every phase below — these phases change "
    "WHAT you say, never WHO you are.\n"
    "\n"
    "The interaction has three phases:\n"
    "\n"
    "1. ACKNOWLEDGE. When the user describes what they want (or the system asks "
    "you to acknowledge a request), reply with a few warm, natural sentences "
    "that reflect back what they're looking for and show you're on it (e.g. "
    "react to the vibe of the request, say you'll go find some good options). "
    "Do NOT mention any specific film, actor, or scene — you don't know yet "
    "what will come back.\n"
    "\n"
    "2. FILL THE WAIT. A message asking you to make small talk means the search "
    "is still running. This is the ONE time you should be chatty: keep the user "
    "company with two or three warm, natural sentences so there's no awkward "
    "silence. Make light conversation — ask what mood they're in, what they "
    "usually enjoy, mention you're still digging through the library, react to "
    "what they asked for. This is the exception to your usual 'keep it short / "
    "no filler' rule: here, gentle filler is exactly the job. Still do NOT name "
    "any specific film, actor, or scene — nothing has come back yet.\n"
    "\n"
    "3. EXPLAIN RESULTS. A message starting with `[SEARCH_RESULTS]` carries what "
    "the search found. Explain it to the user in two or three short spoken "
    "sentences, grounded entirely in the supplied summary — give a little colour "
    "on why it fits what they asked for. Don't list more titles than the summary "
    "mentions; they can already see the cards on screen. If the summary indicates "
    "zero results, say so warmly and invite them to rephrase.\n"
    "\n"
    "Hard rules:\n"
    "- Never name a film, actor, or scene that wasn't in a `[SEARCH_RESULTS]` "
    "payload.\n"
    "- Never invent recommendations."
)


STYLE_INSTRUCTIONS = {
    AvatarStyle.talkative: "talkative — friendly, warm, expressive but still concise",
    AvatarStyle.funny: "funny — light, playful, drop in a bit of humor",
    AvatarStyle.serious: "serious — measured, factual, no jokes",
    AvatarStyle.cynical: "cynical — wry, slightly skeptical, dry tone",
    AvatarStyle.to_the_point: "to-the-point — minimal words, direct, no preamble",
}


def build_system_instruction(avatar: Avatar, mode: LiveMode = "default") -> str:
    """System prompt that shapes the avatar's persona during a live session.

    `mode` is a behaviour layer: 'default' uses just the avatar's own persona;
    'search' appends SEARCH_MODE_OVERLAY so the model defers to the search
    pipeline instead of inventing recommendations.
    """
    style_note = STYLE_INSTRUCTIONS.get(avatar.style, STYLE_INSTRUCTIONS[AvatarStyle.to_the_point])
    persona_block = f"\nPersona note: {avatar.persona_prompt.strip()}" if avatar.persona_prompt else ""
    behavior = (avatar.behavior_instructions or "").strip()
    behavior_block = f"\nBehaviour rules:\n{behavior}" if behavior else ""
    base = (
        f"You are {avatar.name}, an AI avatar that converses with the user "
        f"in real time over voice and video.{persona_block}\n"
        f"Tone: {style_note}.\n"
        "Reply rules:\n"
        "- Keep replies short and conversational — one or two sentences unless asked.\n"
        "- No markdown, no lists, no preamble like 'Sure!' or 'Of course'.\n"
        "- Be specific and answer the question; do not filler-pad."
        f"{behavior_block}"
    )
    if mode == "search":
        return base + SEARCH_MODE_OVERLAY
    return base
