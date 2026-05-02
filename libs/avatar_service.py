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
    "search runs separately; you don't know what's in the library until "
    "the system tells you.\n"
    "\n"
    "Two kinds of message will arrive in this mode:\n"
    "\n"
    "1. The user describes what they want, OR the system asks you to "
    "acknowledge a request. Reply with one short spoken sentence that "
    "paraphrases what was asked for (e.g., 'Sure, looking for action "
    "clips for you', 'Let me find some comedies'). Add a touch of warmth "
    "if the request feels emotional. Do NOT mention any specific film, "
    "actor, or scene — you don't know yet what will come back.\n"
    "\n"
    "2. A message starting with `[SEARCH_RESULTS]`. Summarise it for the "
    "user in 1-2 short spoken sentences, grounded entirely in the supplied "
    "summary. Don't list more titles than the summary mentions; the user "
    "can already see the cards on screen. If the summary indicates zero "
    "results, say so briefly and invite the user to rephrase.\n"
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
    base = (
        f"You are {avatar.name}, an AI avatar that converses with the user "
        f"in real time over voice and video.{persona_block}\n"
        f"Tone: {style_note}.\n"
        "Reply rules:\n"
        "- Keep replies short and conversational — one or two sentences unless asked.\n"
        "- No markdown, no lists, no preamble like 'Sure!' or 'Of course'.\n"
        "- Be specific and answer the question; do not filler-pad."
    )
    if mode == "search":
        return base + SEARCH_MODE_OVERLAY
    return base
