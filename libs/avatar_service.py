"""Avatar service — system-instruction builder for Gemini Live sessions."""

from typing import Literal

from api.models.schemas.avatars import Avatar, AvatarStyle

LiveMode = Literal["default", "search"]

# Layered onto the avatar's normal system instruction when mode=search. The
# rules are deliberately strict and ordered: the model MUST acknowledge the
# user's request out loud BEFORE calling the search_movies tool, then narrate
# the results AFTER the tool returns. Without the ordering, the model
# silently calls the tool and only speaks once when the result lands — the
# user perceives a long unexplained pause.
SEARCH_MODE_OVERLAY = (
    "\n\nMODE: SEARCH ASSISTANT\n"
    "You help the user find movies and clips from a curated library. The "
    "library is searched via the `search_movies` tool — that is the ONLY way "
    "to know what is in the library.\n"
    "\n"
    "For every user request, follow this exact 3-step order. Do NOT skip "
    "step 1 or merge steps:\n"
    "\n"
    "STEP 1 — Acknowledge the user's request out loud, in one short spoken "
    "sentence that paraphrases what they asked for (e.g., 'Sure, looking "
    "for action clips for you', 'Let me find some comedies', 'Looking for "
    "scenes with Tony Stark in space'). One sentence only. Add a touch of "
    "warmth if their request feels emotional. Do NOT say what you'll find — "
    "you don't know yet.\n"
    "\n"
    "STEP 2 — Immediately call the `search_movies` tool with the user's "
    "request as the `query` argument. Multilingual queries are fine; the "
    "tool handles translation. You MUST call the tool — do not skip it and "
    "invent recommendations.\n"
    "\n"
    "STEP 3 — When the tool returns, narrate the results in 1-2 short "
    "spoken sentences, grounded in the tool response's `summary` field. "
    "Don't list more titles than the summary mentions; the user can already "
    "see the cards on screen. If the tool returns zero results, say so "
    "briefly and invite the user to rephrase.\n"
    "\n"
    "Hard rules:\n"
    "- Never name a film, actor, or scene that wasn't in the tool response.\n"
    "- Never call `search_movies` without first acknowledging out loud.\n"
    "- Never invent recommendations before the tool returns."
)

# Tool declaration for the Gemini Live setup frame in mode=search. The
# description steers the model toward calling the tool on movie/clip requests
# rather than free-form chatter; the parameters are intentionally narrow so
# the model can't smuggle extra structured fields we don't read.
SEARCH_TOOL_DECLARATION = {
    "name": "search_movies",
    "description": (
        "Search the curated movie/clip library for content matching the user's "
        "request. Returns a natural-language summary of recommendations plus "
        "a result count. Use this whenever the user describes what they want "
        "to watch — a mood, genre, scene, actor, or any other findable detail."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The user's request, in their own words. Multilingual is "
                    "fine — the search service handles translation."
                ),
            },
        },
        "required": ["query"],
    },
}


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
