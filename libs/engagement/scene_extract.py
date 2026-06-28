"""Extract dialog cues and entity timelines from a scene-analysis job's results.

Two paths:

  1. Structured path (preferred): the scene_analysis job used the structured
     schema in `libs/scene_processing/scene_analysis_schema.py` and each
     chunk's `result_data` carries `summary` / `cues` / `entities` / `events`
     keys. Cues and entities are merged across chunks.

  2. Fallback path: the scene_analysis job emitted free-text or SRT in
     `result_data.raw_text`. Mine cues from SRT cue blocks and characters from
     recurring proper nouns.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Cue:
    start_sec: float
    end_sec: float
    text: str
    kind: str = "dialogue"
    speaker: str = ""
    sentiment: str = ""  # positive / neutral / negative (optional, structured only)


@dataclass
class Entity:
    name: str
    kind: str  # character / object / location / event / emotion
    appearances: List[Tuple[float, float]] = field(default_factory=list)
    mention_count: int = 0
    # Raw intensity samples (emotions / events). avg_intensity() summarizes them.
    intensity_values: List[float] = field(default_factory=list)

    def avg_intensity(self) -> Optional[float]:
        if not self.intensity_values:
            return None
        return sum(self.intensity_values) / len(self.intensity_values)


@dataclass
class Segment:
    """A finer-than-chunk scene beat (from scene-analysis `segments`)."""

    start_sec: float
    end_sec: float
    title: str
    synopsis: str
    location: str = ""


@dataclass
class KeyMoment:
    """A standout narrative beat (from scene-analysis `key_moments`)."""

    start_sec: float
    type: str
    label: str


# Tokens we never want as character names even if they appear capitalized.
_PROPER_NOUN_STOPWORDS = frozenset(
    {
        "Mr",
        "Mrs",
        "Ms",
        "The",
        "You",
        "I",
        "We",
        "They",
        "He",
        "She",
        "It",
        "Who",
        "What",
        "When",
        "Where",
        "Why",
        "How",
        "But",
        "And",
        "Or",
        "If",
        "So",
        "Then",
        "Now",
        "Yes",
        "No",
        "Ok",
        "Okay",
        "God",
        "Lord",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    }
)


def extract_from_scene_results(
    results: List[Dict[str, Any]],
) -> Tuple[List[Cue], List[Entity]]:
    """Walk a scene job's chunk results and return merged (cues, entities).

    Picks the structured path if any chunk's `result_data` has the
    `cues`/`entities`/`events` keys, otherwise falls back to SRT mining of
    `result_data.raw_text` (or `raw_response`).
    """
    if not results:
        return [], []

    if any(_is_structured(r) for r in results):
        return _extract_structured(results)
    return _extract_from_srt(results)


# ── Structured path ──────────────────────────────────────────────


def _is_structured(result: Dict[str, Any]) -> bool:
    rd = result.get("result_data") or {}
    return any(k in rd for k in ("cues", "entities", "events", "emotions"))


def _extract_structured(
    results: List[Dict[str, Any]],
) -> Tuple[List[Cue], List[Entity]]:
    cues: List[Cue] = []
    entities_by_key: Dict[Tuple[str, str], Entity] = {}

    for r in results:
        rd = r.get("result_data") or {}

        for c in rd.get("cues") or []:
            try:
                cue = Cue(
                    start_sec=float(c["start_sec"]),
                    end_sec=float(c["end_sec"]),
                    text=str(c.get("text", "")),
                    kind=str(c.get("kind") or "dialogue"),
                    speaker=str(c.get("speaker") or ""),
                    sentiment=str(c.get("sentiment") or ""),
                )
                cues.append(cue)
            except (KeyError, TypeError, ValueError):
                continue

        for e in rd.get("entities") or []:
            try:
                name = str(e["name"]).strip()
                kind = str(e.get("kind") or "character")
                if not name:
                    continue
                key = (_normalize(name), kind)
                entity = entities_by_key.get(key)
                if entity is None:
                    entity = Entity(name=name, kind=kind, appearances=[], mention_count=0)
                    entities_by_key[key] = entity
                appearances = e.get("appearances") or []
                for app in appearances:
                    rng = _coerce_range(app)
                    if rng is not None:
                        entity.appearances.append(rng)
                        entity.mention_count += 1
            except (KeyError, TypeError, ValueError):
                continue

        # Events are first-class entities of kind="event" — that lets the
        # frontend filter on them with the same chip UI used for characters.
        for ev in rd.get("events") or []:
            try:
                tag = str(ev["tag"]).strip()
                if not tag:
                    continue
                key = (_normalize(tag), "event")
                entity = entities_by_key.get(key)
                if entity is None:
                    entity = Entity(name=tag, kind="event", appearances=[], mention_count=0)
                    entities_by_key[key] = entity
                rng = _coerce_range({"start_sec": ev["start_sec"], "end_sec": ev["end_sec"]})
                if rng is not None:
                    entity.appearances.append(rng)
                    entity.mention_count += 1
                    intensity = _coerce_float(ev.get("intensity"))
                    if intensity is not None:
                        entity.intensity_values.append(intensity)
            except (KeyError, TypeError, ValueError):
                continue

        # Emotions are time-bounded affect segments. Surface each as an entity
        # of kind="emotion" so the engagement-influence delta logic (avg rating
        # during the segment vs overall) and the frontend chip/ranking UI treat
        # them uniformly with characters and events.
        for em in rd.get("emotions") or []:
            try:
                label = str(em["emotion"]).strip()
                if not label:
                    continue
                key = (_normalize(label), "emotion")
                entity = entities_by_key.get(key)
                if entity is None:
                    entity = Entity(name=label, kind="emotion", appearances=[], mention_count=0)
                    entities_by_key[key] = entity
                rng = _coerce_range({"start_sec": em["start_sec"], "end_sec": em["end_sec"]})
                if rng is not None:
                    entity.appearances.append(rng)
                    entity.mention_count += 1
                    intensity = _coerce_float(em.get("intensity"))
                    if intensity is not None:
                        entity.intensity_values.append(intensity)
            except (KeyError, TypeError, ValueError):
                continue

    # Sort cues by start; merge entity appearances within 5s of each other.
    cues.sort(key=lambda c: c.start_sec)
    cues = _dedupe_cues(cues)

    entities = list(entities_by_key.values())
    for ent in entities:
        ent.appearances = _merge_ranges(ent.appearances, gap=5.0)
    entities.sort(key=lambda e: -e.mention_count)
    return cues, entities


def extract_segments(results: List[Dict[str, Any]]) -> List[Segment]:
    """Collect finer-than-chunk scene beats from `segments`, sorted by start.

    Returns [] when no chunk carries a `segments` array (old jobs) — the caller
    falls back to chunk-level `summary`.
    """
    out: List[Segment] = []
    for r in results or []:
        rd = r.get("result_data") or {}
        for seg in rd.get("segments") or []:
            try:
                out.append(
                    Segment(
                        start_sec=float(seg["start_sec"]),
                        end_sec=float(seg["end_sec"]),
                        title=str(seg.get("title") or ""),
                        synopsis=str(seg.get("synopsis") or ""),
                        location=str(seg.get("location") or ""),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    out.sort(key=lambda s: s.start_sec)
    return out


def extract_key_moments(results: List[Dict[str, Any]]) -> List[KeyMoment]:
    """Collect standout beats from `key_moments`, sorted by start."""
    out: List[KeyMoment] = []
    for r in results or []:
        rd = r.get("result_data") or {}
        for m in rd.get("key_moments") or []:
            try:
                kind = str(m["type"]).strip()
                if not kind:
                    continue
                out.append(
                    KeyMoment(
                        start_sec=float(m["start_sec"]),
                        type=kind,
                        label=str(m.get("label") or ""),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    out.sort(key=lambda m: m.start_sec)
    return out


def extract_narrative_beats(results: List[Dict[str, Any]]) -> List[KeyMoment]:
    """Collect classical story beats from `narrative_beats` as point markers.

    Mapped onto KeyMoment (type = beat name, label = supplied label or the beat
    name) so the timeline can render act markers alongside key_moments.
    """
    out: List[KeyMoment] = []
    for r in results or []:
        rd = r.get("result_data") or {}
        for b in rd.get("narrative_beats") or []:
            try:
                beat = str(b["beat"]).strip()
                if not beat:
                    continue
                out.append(
                    KeyMoment(
                        start_sec=float(b["start_sec"]),
                        type=beat,
                        label=str(b.get("label") or beat.replace("_", " ")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    out.sort(key=lambda m: m.start_sec)
    return out


def _coerce_float(value: Any) -> Optional[float]:
    """Parse a numeric cell to float, or None if absent/unparseable."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # drop NaN


def _coerce_range(item: Any) -> Optional[Tuple[float, float]]:
    """Accept either {start_sec, end_sec} or [start, end] forms."""
    try:
        if isinstance(item, dict):
            return (float(item["start_sec"]), float(item["end_sec"]))
        if isinstance(item, (list, tuple)) and len(item) == 2:
            return (float(item[0]), float(item[1]))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _dedupe_cues(cues: List[Cue]) -> List[Cue]:
    """Drop exact-duplicate cues that arise when chunk boundaries overlap."""
    seen: set = set()
    out: List[Cue] = []
    for c in cues:
        key = (round(c.start_sec, 1), round(c.end_sec, 1), c.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ── Fallback path: SRT mining ────────────────────────────────────


_SRT_BLOCK_RE = re.compile(
    r"(?:\d+\s*\n)?"
    r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*\n"
    r"(.*?)(?=\n\s*(?:\d+\s*\n)?\d{1,2}:\d{2}:\d{2}|$)",
    re.DOTALL,
)


def _extract_from_srt(
    results: List[Dict[str, Any]],
) -> Tuple[List[Cue], List[Entity]]:
    raw_text_parts: List[str] = []
    for r in results:
        rd = r.get("result_data") or {}
        text = rd.get("raw_text") or rd.get("raw_response") or ""
        if isinstance(text, str) and text.strip():
            raw_text_parts.append(text)
    full_text = "\n\n".join(raw_text_parts)
    if not full_text:
        return [], []

    cues = _parse_srt_cues(full_text)

    entity_apps: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}
    entity_counts: Dict[Tuple[str, str], int] = {}

    for c in cues:
        # Bracketed cues are events: "[dramatic music]" → "dramatic music"
        bracket_match = re.match(r"^\s*\[(.+?)\]\s*$", c.text.strip(), re.DOTALL)
        if bracket_match:
            tag = bracket_match.group(1).strip().lower()
            key = (tag, "event")
            entity_apps.setdefault(key, []).append((c.start_sec, c.end_sec))
            entity_counts[key] = entity_counts.get(key, 0) + 1
            continue

        # Proper-noun mining for character candidates.
        for token in _proper_noun_tokens(c.text):
            key = (token, "character")
            entity_apps.setdefault(key, []).append((c.start_sec, c.end_sec))
            entity_counts[key] = entity_counts.get(key, 0) + 1

    entities: List[Entity] = []
    for (name, kind), apps in entity_apps.items():
        count = entity_counts[(name, kind)]
        if kind == "character" and count < 3:
            continue  # too rare to be a recurring character
        entities.append(
            Entity(
                name=name if kind == "event" else name,
                kind=kind,
                appearances=_merge_ranges(apps, gap=5.0),
                mention_count=count,
            )
        )
    entities.sort(key=lambda e: -e.mention_count)
    return cues, entities


def _parse_srt_cues(text: str) -> List[Cue]:
    cues: List[Cue] = []
    for m in _SRT_BLOCK_RE.finditer(text):
        try:
            start = _srt_time(m.group(1))
            end = _srt_time(m.group(2))
        except ValueError:
            continue
        body = m.group(3).strip()
        if not body:
            continue
        cues.append(Cue(start_sec=start, end_sec=end, text=body, kind="dialogue", speaker=""))
    cues.sort(key=lambda c: c.start_sec)
    return cues


def _srt_time(value: str) -> float:
    """Parse hh:mm:ss,SSS (or hh:mm:ss.SSS) → float seconds."""
    value = value.replace(",", ".")
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _proper_noun_tokens(text: str) -> Iterable[str]:
    """Yield distinct capitalized tokens that look like character names."""
    seen: set = set()
    for tok in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text):
        if tok in _PROPER_NOUN_STOPWORDS:
            continue
        if tok.lower() in seen:
            continue
        seen.add(tok.lower())
        yield tok


# ── Shared helpers ───────────────────────────────────────────────


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _merge_ranges(ranges: List[Tuple[float, float]], gap: float = 5.0) -> List[Tuple[float, float]]:
    """Merge ranges that are within `gap` seconds of each other."""
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged: List[Tuple[float, float]] = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= gap:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged
