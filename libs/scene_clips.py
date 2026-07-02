"""Project scene-analysis result_data into clip-able scene entries.

Handles BOTH analysis schemas (adapted from the retired search curator's
projections), normalizing each into {start, end, summary, people} with
HH:MM:SS times:
  - scene schema: `scenes[]` with start_time/end_time (HH:MM:SS strings)
  - event schema: `events[]` with start_sec/end_sec (numeric) + description

Used at sync time to index one embedding row per scene, so vector search
retrieves the specific moment a query is about and ranking can emit `clip`
recommendations without an LLM.
"""

from typing import Any, Optional

# Cap scene rows per result to bound sync cost; analyses rarely exceed this.
MAX_SCENES_PER_RESULT = 12


def _clip_time(t: Any) -> Optional[str]:
    """Normalize a scene time like '00:00:07.200' to 'HH:MM:SS' (drop millis)."""
    if not isinstance(t, str) or not t.strip():
        return None
    return t.strip().split(".")[0]


def _sec_to_hhmmss(s: Any) -> Optional[str]:
    """Convert a numeric second offset (e.g. 44.0) to 'HH:MM:SS'."""
    try:
        total = int(float(s))
    except (TypeError, ValueError):
        return None
    if total < 0:
        return None
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _from_scene_schema(scenes: list) -> list[dict]:
    entries: list[dict] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        summary = scene.get("summary")
        if not (isinstance(summary, str) and summary.strip()):
            continue
        people = [
            person.get("label", "")
            for person in scene.get("people", []) or []
            if isinstance(person, dict) and person.get("label") and not person.get("label", "").startswith("Person")
        ]
        entries.append(
            {
                "start": _clip_time(scene.get("start_time")),
                "end": _clip_time(scene.get("end_time")),
                "summary": summary.strip(),
                "people": people[:4],
            }
        )
    return entries


def _from_event_schema(events: list) -> list[dict]:
    entries: list[dict] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        desc = ev.get("description")
        if not (isinstance(desc, str) and desc.strip()):
            continue
        entry: dict[str, Any] = {
            "start": _sec_to_hhmmss(ev.get("start_sec")),
            "end": _sec_to_hhmmss(ev.get("end_sec")),
            "summary": desc.strip(),
            "people": [],
        }
        tag = ev.get("tag")
        if isinstance(tag, str) and tag.strip():
            entry["summary"] = f"{tag.strip()}: {entry['summary']}"
        entries.append(entry)
    return entries


def extract_scene_entries(result_data: dict, max_scenes: int = MAX_SCENES_PER_RESULT) -> list[dict]:
    """Extract clip-able scene entries from either analysis schema.

    Only entries with BOTH start and end times are returned — a scene row
    without times can't produce a clip recommendation, and the whole-video
    row already covers its text.
    """
    scenes, events = result_data.get("scenes"), result_data.get("events")
    if isinstance(scenes, list) and scenes:
        entries = _from_scene_schema(scenes)
    elif isinstance(events, list) and events:
        entries = _from_event_schema(events)
    else:
        return []
    return [e for e in entries if e["start"] and e["end"] and e["start"] != e["end"]][:max_scenes]


def build_scene_text(entry: dict, result_data: dict) -> str:
    """Embedding text for one scene row: video-level classification for
    context, then the scene's own summary and named people."""
    parts: list[str] = []
    for key in ("genre", "type", "content_type"):
        val = result_data.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(f"{key.replace('_', ' ').title()}: {val.strip()}")
    parts.append(entry["summary"])
    if entry.get("people"):
        parts.append("People: " + ", ".join(entry["people"]))
    return " ".join(parts)
