"""Structured-output schema and seeded prompt for the `scene_analysis` category.

Single source of truth for the JSON shape Gemini emits when the seeded
`Scene Analysis (Structured)` prompt is selected for a scene job. Downstream,
`libs/engagement/scene_extract.py` reads this same shape to build entity and
cue timelines for engagement analytics.
"""

from typing import Any, Dict


# Gemini-compatible JSON Schema. Uses only: type, properties, required, items,
# enum, description, minItems, maxItems. No $ref / oneOf / additionalProperties.
SCENE_ANALYSIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["summary", "cues", "entities", "events"],
    "properties": {
        "summary": {
            "type": "string",
            "description": ("One-paragraph synopsis of what happens in this chunk (3-6 sentences)."),
        },
        "cues": {
            "type": "array",
            "description": ("Dialog, narration, and timed audio events covering the chunk."),
            "items": {
                "type": "object",
                "required": ["start_sec", "end_sec", "text", "kind"],
                "properties": {
                    "start_sec": {
                        "type": "number",
                        "description": ("Absolute start time in seconds from t=0 of the full source video."),
                    },
                    "end_sec": {
                        "type": "number",
                        "description": ("Absolute end time in seconds from t=0 of the full source video."),
                    },
                    "speaker": {
                        "type": "string",
                        "description": (
                            "Speaking character's name for dialogue cues. Empty string if "
                            "narration, music, sfx, silence, or unknown."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "Verbatim line for dialogue/narration; bracketed description for "
                            "non-verbal cues (e.g. '[dramatic orchestral swell]')."
                        ),
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["dialogue", "narration", "music", "sfx", "silence"],
                    },
                },
            },
        },
        "entities": {
            "type": "array",
            "description": ("Named characters, props, and locations that appear in this chunk."),
            "items": {
                "type": "object",
                "required": ["name", "kind", "appearances"],
                "properties": {
                    "name": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["character", "object", "location"],
                    },
                    "description": {
                        "type": "string",
                        "description": ("Short identifying phrase (e.g. 'young protagonist, blue tunic')."),
                    },
                    "appearances": {
                        "type": "array",
                        "description": (
                            "Contiguous on-screen ranges within this chunk. Merge ranges "
                            "within 2 seconds of each other."
                        ),
                        "items": {
                            "type": "object",
                            "required": ["start_sec", "end_sec"],
                            "properties": {
                                "start_sec": {"type": "number"},
                                "end_sec": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "events": {
            "type": "array",
            "description": "Tagged narrative or audio events with absolute time bounds.",
            "items": {
                "type": "object",
                "required": ["tag", "start_sec", "end_sec"],
                "properties": {
                    "tag": {
                        "type": "string",
                        "enum": [
                            "action",
                            "dialogue_heavy",
                            "music",
                            "comedy",
                            "tension",
                            "exposition",
                            "climax",
                            "transition",
                            "song",
                            "fight",
                            "romance",
                            "emotional",
                        ],
                    },
                    "description": {
                        "type": "string",
                        "description": ("One short sentence anchoring the event in concrete content."),
                    },
                    "start_sec": {"type": "number"},
                    "end_sec": {"type": "number"},
                },
            },
        },
        "narrative_beats": {
            "type": "array",
            "description": ("Optional. Emit only when a classical story beat clearly starts in this chunk."),
            "items": {
                "type": "object",
                "required": ["beat", "start_sec", "end_sec"],
                "properties": {
                    "beat": {
                        "type": "string",
                        "enum": [
                            "setup",
                            "inciting_incident",
                            "rising_action",
                            "climax",
                            "falling_action",
                            "resolution",
                        ],
                    },
                    "start_sec": {"type": "number"},
                    "end_sec": {"type": "number"},
                },
            },
        },
    },
}


SCENE_ANALYSIS_PROMPT_NAME = "Scene Analysis (Structured)"

# `{chunk_start_sec}` and `{chunk_end_sec}` are substituted by the scene
# processor (sequential.py / parallel.py) before each Gemini call.
SCENE_ANALYSIS_PROMPT_TEXT = """\
You are an expert video scene analyst. You will be shown a chunk of a longer
video. Produce ONE structured JSON object matching the supplied response
schema. No prose outside the JSON.

## Time conventions
- Every timestamp you emit MUST be in absolute video seconds (i.e. measured
  from t=0 of the FULL source video, not from the start of this chunk).
- This chunk covers seconds {chunk_start_sec} to {chunk_end_sec} of the source
  video. All start_sec / end_sec / appearance values you emit must lie inside
  this range.
- Use floats with one decimal where useful (e.g. 73.5). Never invent times for
  things you did not directly observe.

## summary
- One paragraph (3-6 sentences) describing what happens in this chunk in plain
  language. Mention the named characters who actually appear and the dominant
  events (action, dialog, song, etc.).

## cues  (dialog + narration + audio events with timing)
- Emit one cue per discrete spoken line, voiceover, song segment, music cue,
  sound effect, or stretch of pure silence (>3s).
- `text` should be the spoken/sung line verbatim where possible. For non-verbal
  cues, describe in brackets, e.g. "[dramatic orchestral swell]",
  "[crowd cheers]", "[silence]".
- `kind` must be one of: dialogue, narration, music, sfx, silence.
- `speaker` is the on-screen character's name for dialogue cues; "" otherwise.
  Do NOT guess speaker names - leave "" if you are not confident.
- Cues should not overlap. Adjacent cues should be contiguous (next cue's
  start_sec ~= previous cue's end_sec).

## entities  (recurring named participants and important props/locations)
- List every named character who speaks or is clearly identified on screen in
  this chunk. Also list named locations and meaningful props that recur.
- `kind` must be one of: character, object, location.
- `appearances` is an array of objects {start_sec, end_sec} giving every
  contiguous range in this chunk where the entity is on screen (or, for an
  off-screen but actively-named character, every range where they are being
  addressed / discussed). Merge ranges that are within 2 seconds of each other.
- `description` is one short sentence (e.g. "young protagonist, blue tunic").
- IMPORTANT: re-list every entity each chunk where it appears. Downstream
  merging unions appearances across chunks; an entity omitted in a chunk is
  treated as absent there.

## events  (tagged narrative / audio events)
- A timed segment with a categorical tag describing what kind of beat it is.
- `tag` must be one of: action, dialogue_heavy, music, comedy, tension,
  exposition, climax, transition, song, fight, romance, emotional.
- A single chunk typically yields 2-10 events. Events may overlap (e.g. a song
  during a fight). Use the tightest time bounds you can.
- `description` is one short sentence anchoring the event in concrete content
  (e.g. "Ganesh confronts the demon king as the score swells").

## narrative_beats  (optional, only when clearly observable)
- If this chunk contains the start of a classical story beat (setup, inciting
  incident, rising action, climax, falling action, resolution), emit it.
- Skip if uncertain. Better to omit than to mislabel.

## Quality bar
- Be specific. "A character speaks" is useless; name them, quote a line.
- Do not invent. If audio is unclear, say "[unclear dialogue]" and lower your
  confidence rather than guessing names.
- Cover the entire chunk. A chunk with no cues or no events is almost always a
  signal you missed something - re-watch and try again.
- Output strictly valid JSON conforming to the response schema. No markdown
  fences, no commentary.
"""


def render_prompt(prompt_text: str, chunk_start_sec: float, chunk_end_sec: float) -> str:
    """Substitute the `{chunk_start_sec}` / `{chunk_end_sec}` placeholders.

    Safe to call on any prompt: placeholders that are absent are no-ops.
    """
    return prompt_text.replace("{chunk_start_sec}", f"{chunk_start_sec:.1f}").replace(
        "{chunk_end_sec}", f"{chunk_end_sec:.1f}"
    )
