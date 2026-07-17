"""Fact-constrained Gemini narration stage (Epic 4, story 2).

Feeds the verified event timeline (the ``fuse`` stage output) plus the clip
to Gemini via the shared ``libs.gemini.SceneAnalyzer``, producing prose in the
established analysis format (Timestamp / Event Title / Analysis / Category)
that never contradicts or invents facts — signals own the timestamps and
facts, the LLM owns only the meaning.

Constraints enforced here:

* **Gated off by default** — ``BasketballSettings.narrate_enabled`` is False
  unless the CLI is invoked with ``--narrate``; the disabled path writes a
  ``{"narrated": false}`` marker and never touches ``libs.gemini``.
* **Lazy network imports** — ``libs.gemini`` (google-genai + the repo root
  ``config.py`` with its required GCP env) is only imported inside
  ``_make_analyzer``, so the offline pipeline and unit tests never need it.
* **Post-validation** — each narration entry must echo its event's facts;
  echoes are checked against the timeline (t within ±2 s, exact team /
  points / jersey where non-null, entry count == event count). A violating
  response is retried once with the violations appended to the prompt; a
  second failure falls back to deterministic templated text per event.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from libs.basketball.config import BasketballSettings
from libs.basketball.timeline import Event, predictions_from_dict

logger = logging.getLogger(__name__)

# Echoed timestamps may deviate from the timeline by at most this much.
ECHO_T_TOLERANCE_SEC = 2.0

# Attributes echoed back by the model and validated exactly when non-null.
_EXACT_ECHO_ATTRS = ("team", "points", "jersey")

RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "timestamp_range": {"type": "string"},
            "event_title": {"type": "string"},
            "analysis": {"type": "string"},
            "category": {"type": "string"},
            "echo": {
                "type": "object",
                "properties": {
                    "t": {"type": "number"},
                    "outcome": {"type": "string", "nullable": True},
                    "team": {"type": "string", "nullable": True},
                    "points": {"type": "integer", "nullable": True},
                    "jersey": {"type": "string", "nullable": True},
                },
                "required": ["t"],
            },
        },
        "required": ["timestamp_range", "event_title", "analysis", "category", "echo"],
    },
}


# --- Fact block + prompt -----------------------------------------------------


def sort_events(events: List[Event]) -> List[Event]:
    """Deterministic event order: by start time (stable for ties)."""
    return sorted(events, key=lambda e: e.t)


def _format_time_range(event: Event) -> str:
    if event.t_end is not None:
        return f"{event.t:.1f}s-{event.t_end:.1f}s"
    return f"{event.t:.1f}s"


def build_fact_block(events: List[Event]) -> str:
    """One deterministic line per event; null attributes are omitted entirely."""
    lines = []
    for index, event in enumerate(sort_events(events), start=1):
        parts = [f"Event {index}", f"t={_format_time_range(event)}", f"type={event.type}"]
        if event.outcome is not None:
            parts.append(f"outcome={event.outcome}")
        if event.team is not None:
            parts.append(f"team={event.team}")
        if event.points is not None:
            parts.append(f"points={event.points}")
        if event.jersey is not None:
            parts.append(f"jersey={event.jersey}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def build_prompt(events: List[Event], violations: Optional[List[str]] = None) -> str:
    """Prompt embedding the timeline as ground truth, plus retry feedback."""
    ordered = sort_events(events)
    lines = [
        "You are a professional basketball analyst narrating a broadcast clip.",
        "A deterministic video-analysis pipeline has already extracted the verified",
        "event timeline below from the attached clip. Those facts are ground truth;",
        "your job is only to write the prose around them.",
        "",
        "VERIFIED EVENTS (ground truth):",
        build_fact_block(ordered),
        "",
        "RULES:",
        f"1. Return EXACTLY {len(ordered)} entries — one per verified event, in the order listed.",
        "2. The verified facts are ground truth. Never contradict them.",
        "3. NEVER invent events, timestamps, teams, jersey numbers, or point values",
        "   that are not in the verified list.",
        "4. If an attribute is absent from an event's line it is unknown: omit it from",
        "   your prose rather than guessing, and set it to null in the echo object.",
        "5. Use the clip only to describe the play context surrounding each verified",
        "   event (ball movement, defensive pressure, pace, crowd reaction).",
        "6. Per entry: 'timestamp_range' is the event's verified time range as listed;",
        "   'event_title' is a short headline; 'analysis' is 2-4 sentences of prose;",
        "   'category' is a short label such as 'Shot', 'Free Throw' or 'Score Change'.",
        "7. Fill each entry's 'echo' object with that event's verified facts exactly as",
        "   listed ('t' = the event's start time in seconds; null for absent attributes).",
    ]
    if violations:
        lines += [
            "",
            "YOUR PREVIOUS ATTEMPT WAS REJECTED because it violated the verified facts:",
            *[f"- {violation}" for violation in violations],
            "Fix these violations. Echo the verified facts exactly as listed above.",
        ]
    return "\n".join(lines)


# --- Response extraction + validation ----------------------------------------


def extract_entries(result: Any) -> Optional[List[Dict[str, Any]]]:
    """Pull the entry list out of ``SceneAnalyzer.analyze_chunk``'s return value.

    With a top-level array ``response_schema`` the analyzer cannot attach its
    metadata to the parsed list, so the JSON text comes back under
    ``raw_response`` — parse it here. Returns None when no list can be found.
    """
    if isinstance(result, list):
        return result
    if not isinstance(result, dict) or result.get("blocked"):
        return None
    if isinstance(result.get("entries"), list):
        return result["entries"]
    raw = result.get("raw_response")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("entries"), list):
            return parsed["entries"]
    return None


def validate_entries(
    entries: Optional[List[Dict[str, Any]]],
    events: List[Event],
    tolerance_sec: float = ECHO_T_TOLERANCE_SEC,
) -> List[str]:
    """Check echoed facts against the timeline; returns [] when compliant.

    Rules: entry count == event count; echoed t within ±tolerance of the
    event's t; team/points/jersey exactly equal wherever the timeline has a
    non-null value.
    """
    if entries is None:
        return ["response did not contain a parseable list of narration entries"]
    ordered = sort_events(events)
    violations = []
    if len(entries) != len(ordered):
        violations.append(f"entry count {len(entries)} != verified event count {len(ordered)}")
    for index, (entry, event) in enumerate(zip(entries, ordered), start=1):
        echo = entry.get("echo") if isinstance(entry, dict) else None
        if not isinstance(echo, dict):
            violations.append(f"entry {index}: missing 'echo' object")
            continue
        t = echo.get("t")
        if not isinstance(t, (int, float)) or isinstance(t, bool):
            violations.append(f"entry {index}: echo.t missing or not a number")
        elif abs(float(t) - event.t) > tolerance_sec:
            violations.append(
                f"entry {index}: echo.t={float(t):g} deviates from verified t={event.t:g} "
                f"by more than ±{tolerance_sec:g}s"
            )
        for attr in _EXACT_ECHO_ATTRS:
            expected = getattr(event, attr)
            if expected is None:
                continue
            actual = echo.get(attr)
            if attr == "points":
                matches = isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual == expected
            else:
                matches = actual is not None and str(actual) == str(expected)
            if not matches:
                violations.append(f"entry {index}: echo.{attr}={actual!r} != verified {attr}={expected!r}")
    return violations


# --- Templated fallback -------------------------------------------------------


def _echo_facts(event: Event) -> Dict[str, Any]:
    return {
        "t": event.t,
        "outcome": event.outcome,
        "team": event.team,
        "points": event.points,
        "jersey": event.jersey,
    }


def _fallback_category(event: Event) -> str:
    return event.type.replace("_", " ").title()


def _fallback_title(event: Event) -> str:
    words = []
    if event.outcome is not None:
        words.append(event.outcome)
    if event.points is not None:
        words.append(f"{event.points}-point")
    words.append(event.type.replace("_", " "))
    title = " ".join(words)
    return title[0].upper() + title[1:]


def _fallback_analysis(event: Event) -> str:
    facts = [f"type: {event.type}"]
    if event.outcome is not None:
        facts.append(f"outcome: {event.outcome}")
    if event.team is not None:
        facts.append(f"team: {event.team}")
    if event.points is not None:
        facts.append(f"points: {event.points}")
    if event.jersey is not None:
        facts.append(f"jersey: {event.jersey}")
    return (
        f"At {_format_time_range(event)}: {'; '.join(facts)}. "
        "Templated narration generated from the verified facts only."
    )


def build_fallback_entries(events: List[Event]) -> List[Dict[str, Any]]:
    """Deterministic per-event entries used when Gemini output fails validation."""
    return [
        {
            "timestamp_range": _format_time_range(event),
            "event_title": _fallback_title(event),
            "analysis": _fallback_analysis(event),
            "category": _fallback_category(event),
            "echo": _echo_facts(event),
        }
        for event in sort_events(events)
    ]


# --- Gemini interaction --------------------------------------------------------


def _make_analyzer(settings: BasketballSettings):
    """Build the shared SceneAnalyzer.

    Lazy import on purpose: ``libs.gemini`` pulls in google-genai and the repo
    root ``config.py`` (required GCP env vars) — neither exists in the default
    offline environment, so this must only run when narration is enabled.
    """
    try:
        from libs.gemini import SceneAnalyzer
        from libs.gemini.common import model_name
    except Exception as exc:  # missing google-genai, or root config env validation
        raise RuntimeError(
            "--narrate needs the optional Gemini dependencies and GCP config: install "
            "google-genai + google-api-core (see requirements-basketball.txt) and set the "
            "repo root config.py env vars (GCP_PROJECT_ID, buckets, ADC). "
            f"Underlying error: {exc}"
        ) from exc

    analyzer = SceneAnalyzer()
    if settings.narrate_model:
        analyzer.model_name = model_name(settings.narrate_model)
    return analyzer


def _accumulate_usage(usage: Dict[str, Any], token_usage: Optional[Dict[str, Any]]) -> None:
    if not token_usage:
        return
    usage["tokens"] += int(token_usage.get("total_tokens", 0) or 0)
    usage["estimated_cost_usd"] = round(
        usage["estimated_cost_usd"] + float(token_usage.get("estimated_cost_usd", 0.0) or 0.0), 6
    )


def narrate_events(
    clip_path: Path,
    events: List[Event],
    settings: BasketballSettings,
    analyzer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run the fact-constrained narration loop and return the stage output dict."""
    ordered = sort_events(events)
    usage: Dict[str, Any] = {"tokens": 0, "estimated_cost_usd": 0.0}

    if not ordered:
        logger.info("narrate: timeline has no events — nothing to narrate")
        return {
            "narrated": True,
            "model": "",
            "entries": [],
            "usage": usage,
            "fallback": False,
            "violations": [],
        }

    if analyzer is None:
        analyzer = _make_analyzer(settings)

    entries: Optional[List[Dict[str, Any]]] = None
    all_violations: List[str] = []
    violations: List[str] = []
    fallback = False
    attempts = 1 + max(0, settings.narrate_max_retries)

    for attempt in range(1, attempts + 1):
        prompt = build_prompt(ordered, violations=violations or None)
        result = analyzer.analyze_chunk(
            media_path=clip_path,
            chunk_index=0,
            chunk_duration=max(e.t_end if e.t_end is not None else e.t for e in ordered),
            prompt_text=prompt,
            prompt_type="basketball_narration",
            response_schema=RESPONSE_SCHEMA,
        )
        _accumulate_usage(usage, result.get("token_usage") if isinstance(result, dict) else None)
        candidate = extract_entries(result)
        violations = validate_entries(candidate, ordered)
        if not violations:
            entries = candidate
            break
        all_violations.extend(f"attempt {attempt}: {violation}" for violation in violations)
        logger.warning("narrate: attempt %d rejected with %d violation(s)", attempt, len(violations))

    if entries is None:
        logger.warning("narrate: all %d attempt(s) rejected — using templated fallback", attempts)
        entries = build_fallback_entries(ordered)
        fallback = True

    return {
        "narrated": True,
        "model": getattr(analyzer, "model_name", ""),
        "entries": entries,
        "usage": usage,
        "fallback": fallback,
        "violations": all_violations,
    }


# --- Stage entry point ----------------------------------------------------------


def run_stage(ctx) -> None:  # ctx: libs.basketball.stages.StageContext
    """The ``narrate`` pipeline stage (see libs/basketball/stages.py contract)."""
    settings: BasketballSettings = ctx.settings
    if not settings.narrate_enabled:
        logger.info("narrate: disabled (pass --narrate to enable) — writing marker")
        ctx.cache.write_json(ctx.stage, {"narrated": False, "reason": "disabled"})
        return

    # Upstream timeline: the fuse stage's predictions-format output.
    _, events = predictions_from_dict(ctx.cache.read_json("fuse"))
    output = narrate_events(ctx.clip_path, events, settings)
    logger.info(
        "narrate: %d entr%s (fallback=%s, tokens=%d, cost=$%.6f)",
        len(output["entries"]),
        "y" if len(output["entries"]) == 1 else "ies",
        output["fallback"],
        output["usage"]["tokens"],
        output["usage"]["estimated_cost_usd"],
    )
    ctx.cache.write_json(ctx.stage, output)
