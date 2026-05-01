"""Avatar service — system-instruction builder for Gemini Live sessions."""

from api.models.schemas.avatars import Avatar, AvatarStyle


STYLE_INSTRUCTIONS = {
    AvatarStyle.talkative: "talkative — friendly, warm, expressive but still concise",
    AvatarStyle.funny: "funny — light, playful, drop in a bit of humor",
    AvatarStyle.serious: "serious — measured, factual, no jokes",
    AvatarStyle.cynical: "cynical — wry, slightly skeptical, dry tone",
    AvatarStyle.to_the_point: "to-the-point — minimal words, direct, no preamble",
}


def build_system_instruction(avatar: Avatar) -> str:
    """System prompt that shapes the avatar's persona during a live session."""
    style_note = STYLE_INSTRUCTIONS.get(avatar.style, STYLE_INSTRUCTIONS[AvatarStyle.to_the_point])
    persona_block = f"\nPersona note: {avatar.persona_prompt.strip()}" if avatar.persona_prompt else ""
    return (
        f"You are {avatar.name}, an AI avatar that converses with the user "
        f"in real time over voice and video.{persona_block}\n"
        f"Tone: {style_note}.\n"
        "Reply rules:\n"
        "- Keep replies short and conversational — one or two sentences unless asked.\n"
        "- No markdown, no lists, no preamble like 'Sure!' or 'Of course'.\n"
        "- Be specific and answer the question; do not filler-pad."
    )
