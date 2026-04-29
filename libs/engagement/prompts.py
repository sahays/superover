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

RECOMMENDATIONS_PROMPT_TEXT = (
    "You are an audience-engagement consultant for video content.\n\n"
    "You will receive deterministic statistics from the show: the overall\n"
    "average rating, the producer's target average (top-quartile of observed\n"
    "minutes), the top entities/events with positive engagement deltas, the\n"
    "top entities/events with negative deltas, and the best/worst minute\n"
    "buckets with the dialog cues that span them.\n\n"
    "Produce concrete, prescriptive guidance to lift the show's overall\n"
    "rating from `overall_avg` to at least `target_avg`. Output is a single\n"
    "JSON object matching the supplied response schema.\n\n"
    "Rules:\n"
    " - Every `do_more_of` and `do_less_of` recommendation MUST cite an\n"
    "   entity, event, or minute window from the supplied stats. Never invent\n"
    "   characters, props, or events that aren't in the input.\n"
    " - `evidence.delta_pct` and `sample_size` must echo the input numbers.\n"
    " - `anchor_timestamps` must be values that appear in the supplied stats\n"
    "   (entity appearance starts or minute-bucket starts).\n"
    " - `expected_lift` is your judgement: 'high' if the cited entity has\n"
    "   strong delta and large coverage, 'low' if small effect or sample.\n"
    " - `headline` is one tight sentence summarizing the highest-leverage\n"
    "   change, e.g. 'Lean into the Ganesh-Shiva arcs and trim silent\n"
    "   exposition in minutes 12-18.'\n"
    " - `per_minute_callouts` only for minutes the producer should change.\n"
    "   Each callout names what happened, why engagement dipped, and a\n"
    "   concrete alternative grounded in patterns from the high-engagement\n"
    "   minutes.\n"
    " - Be specific and actionable. Avoid generic advice like 'increase\n"
    "   tension' without naming who or what."
)

RECOMMENDATIONS_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["headline", "do_more_of", "do_less_of"],
    "properties": {
        "headline": {
            "type": "string",
            "description": "One-sentence highest-leverage change for this video.",
        },
        "do_more_of": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["recommendation", "rationale", "expected_lift"],
                "properties": {
                    "recommendation": {"type": "string"},
                    "rationale": {"type": "string"},
                    "expected_lift": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "entity": {"type": "string"},
                            "delta_pct": {"type": "number"},
                            "sample_size": {"type": "integer"},
                            "anchor_timestamps": {
                                "type": "array",
                                "items": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "do_less_of": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["recommendation", "rationale", "expected_lift"],
                "properties": {
                    "recommendation": {"type": "string"},
                    "rationale": {"type": "string"},
                    "expected_lift": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "entity": {"type": "string"},
                            "delta_pct": {"type": "number"},
                            "sample_size": {"type": "integer"},
                            "anchor_timestamps": {
                                "type": "array",
                                "items": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "per_minute_callouts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "minute_start_sec",
                    "minute_end_sec",
                    "what_happened",
                    "why_it_dipped",
                    "alternative",
                ],
                "properties": {
                    "minute_start_sec": {"type": "number"},
                    "minute_end_sec": {"type": "number"},
                    "what_happened": {"type": "string"},
                    "why_it_dipped": {"type": "string"},
                    "alternative": {"type": "string"},
                },
            },
        },
    },
}


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
