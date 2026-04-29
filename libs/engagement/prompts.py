"""Engagement analysis prompt template + structured response schema."""

ENGAGEMENT_PROMPT_NAME = "Engagement Peak/Valley Explainer"
ENGAGEMENT_PROMPT_TYPE = "engagement_analysis"

ENGAGEMENT_PROMPT_TEXT = (
    "You are analyzing audience engagement for a video. You will receive: \n"
    "1. The TOP-3 highest engagement moments and TOP-3 lowest engagement moments\n"
    "   (each with a timestamp in seconds and an engagement score from BARC).\n"
    "2. The relevant scene-analysis context from each of those moments.\n\n"
    "For each moment, write:\n"
    " - scene_summary: a tight one-paragraph summary of what is happening at that\n"
    "   timestamp, drawn strictly from the supplied scene-analysis context.\n"
    " - explanation: a concrete hypothesis for WHY this moment is a peak (or valley)\n"
    "   in audience engagement, grounded in the scene context. Reference specific\n"
    "   actors, events, dialog beats, or visual elements.\n"
    " - key_actors / key_events / key_objects: short lists of the most notable\n"
    "   contributors (people, plot beats, props or visuals).\n\n"
    "Be specific. Avoid generic phrases like 'high tension' or 'emotional moment'\n"
    "without naming what produces them. If the scene context is thin or missing,\n"
    "say so plainly in the explanation rather than inventing details."
)

ENGAGEMENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "peaks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "timestamp_sec": {"type": "number"},
                    "scene_summary": {"type": "string"},
                    "explanation": {"type": "string"},
                    "key_actors": {"type": "array", "items": {"type": "string"}},
                    "key_events": {"type": "array", "items": {"type": "string"}},
                    "key_objects": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["rank", "timestamp_sec", "scene_summary", "explanation"],
            },
        },
        "valleys": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "timestamp_sec": {"type": "number"},
                    "scene_summary": {"type": "string"},
                    "explanation": {"type": "string"},
                    "key_actors": {"type": "array", "items": {"type": "string"}},
                    "key_events": {"type": "array", "items": {"type": "string"}},
                    "key_objects": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["rank", "timestamp_sec", "scene_summary", "explanation"],
            },
        },
    },
    "required": ["peaks", "valleys"],
}
