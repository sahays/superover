"""Tests for libs/engagement/scene_extract.py."""

import pytest

from libs.engagement.scene_extract import (
    extract_from_scene_results,
)


pytestmark = pytest.mark.unit


# ── Structured path ──────────────────────────────────────────────


def test_structured_path_merges_entities_across_chunks():
    """An entity present in multiple chunks should have all its appearance
    ranges unioned and ranges within 5s merged."""
    results = [
        {
            "result_data": {
                "cues": [],
                "entities": [
                    {"name": "Ganesh", "kind": "character", "appearances": [{"start_sec": 10.0, "end_sec": 20.0}]},
                ],
                "events": [],
            }
        },
        {
            "result_data": {
                "cues": [],
                "entities": [
                    {
                        "name": "Ganesh",
                        "kind": "character",
                        "appearances": [
                            {"start_sec": 22.0, "end_sec": 30.0},  # within 5s of (10,20) → merge
                            {"start_sec": 60.0, "end_sec": 75.0},  # separate range
                        ],
                    },
                ],
                "events": [],
            }
        },
    ]
    cues, entities = extract_from_scene_results(results)
    assert cues == []
    assert len(entities) == 1
    ent = entities[0]
    assert ent.name == "Ganesh"
    assert ent.kind == "character"
    assert ent.appearances == [(10.0, 30.0), (60.0, 75.0)]
    assert ent.mention_count == 3  # one + two appearances submitted


def test_structured_path_orders_cues_globally():
    """Cues from later chunks may have earlier timestamps if chunks are
    processed out of order. Output must be sorted by start_sec."""
    results = [
        {
            "result_data": {
                "cues": [
                    {"start_sec": 100.0, "end_sec": 105.0, "text": "B", "kind": "dialogue"},
                ],
                "entities": [],
                "events": [],
            }
        },
        {
            "result_data": {
                "cues": [
                    {"start_sec": 0.0, "end_sec": 5.0, "text": "A", "kind": "dialogue"},
                    {"start_sec": 50.0, "end_sec": 55.0, "text": "M", "kind": "music"},
                ],
                "entities": [],
                "events": [],
            }
        },
    ]
    cues, _ = extract_from_scene_results(results)
    assert [c.text for c in cues] == ["A", "M", "B"]


def test_structured_path_lifts_events_to_entities():
    """Events become entities of kind='event' so the chip filter UI can show them."""
    results = [
        {
            "result_data": {
                "cues": [],
                "entities": [],
                "events": [
                    {"tag": "fight", "start_sec": 30.0, "end_sec": 45.0, "description": "swordfight"},
                    {"tag": "fight", "start_sec": 200.0, "end_sec": 220.0},
                    {"tag": "song", "start_sec": 60.0, "end_sec": 90.0},
                ],
            }
        },
    ]
    _, entities = extract_from_scene_results(results)
    by_name = {e.name: e for e in entities}
    assert "fight" in by_name
    assert by_name["fight"].kind == "event"
    assert by_name["fight"].mention_count == 2
    assert by_name["song"].mention_count == 1


def test_structured_path_handles_array_appearance_form():
    """Defensive: accept [start, end] arrays in appearances too, not just objects."""
    results = [
        {
            "result_data": {
                "cues": [],
                "entities": [
                    {"name": "Hero", "kind": "character", "appearances": [[5, 15]]},
                ],
                "events": [],
            }
        }
    ]
    _, entities = extract_from_scene_results(results)
    assert entities[0].appearances == [(5.0, 15.0)]


def test_structured_path_dedupes_overlapping_cues():
    """Cues that repeat at chunk boundaries (same start/end/text) get deduped."""
    results = [
        {
            "result_data": {
                "cues": [
                    {"start_sec": 100.0, "end_sec": 105.0, "text": "Hello", "kind": "dialogue"},
                ],
                "entities": [],
                "events": [],
            }
        },
        {
            "result_data": {
                "cues": [
                    {"start_sec": 100.0, "end_sec": 105.0, "text": "Hello", "kind": "dialogue"},
                ],
                "entities": [],
                "events": [],
            }
        },
    ]
    cues, _ = extract_from_scene_results(results)
    assert len(cues) == 1


# ── Fallback path: SRT mining ────────────────────────────────────


def test_fallback_to_srt_when_no_structured_keys():
    srt = (
        "1\n"
        "00:00:05,000 --> 00:00:10,000\n"
        "[dramatic music]\n\n"
        "2\n"
        "00:00:11,000 --> 00:00:15,500\n"
        "Ganesh, please listen.\n\n"
        "3\n"
        "00:00:30,000 --> 00:00:34,000\n"
        "Ganesh approaches the temple.\n\n"
        "4\n"
        "00:00:60,000 --> 00:00:65,000\n"
        "Ganesh smiles gently.\n"
    )
    results = [{"result_data": {"raw_text": srt}}]
    cues, entities = extract_from_scene_results(results)

    assert len(cues) >= 4
    assert cues[0].start_sec == 5.0
    assert cues[0].end_sec == 10.0

    # Bracketed cue becomes an event entity
    by_name = {e.name: e for e in entities}
    assert "dramatic music" in by_name
    assert by_name["dramatic music"].kind == "event"

    # Ganesh appears 3 times → recognized as a character
    assert "Ganesh" in by_name
    assert by_name["Ganesh"].kind == "character"
    assert by_name["Ganesh"].mention_count == 3


def test_fallback_filters_below_min_mentions():
    """Proper nouns appearing fewer than 3 times must NOT become character entities."""
    srt = (
        "1\n00:00:00,000 --> 00:00:02,000\nGanesh speaks.\n\n"
        "2\n00:00:05,000 --> 00:00:07,000\nGanesh speaks again.\n\n"
        "3\n00:00:10,000 --> 00:00:12,000\nMary just shows up once.\n"
    )
    results = [{"result_data": {"raw_text": srt}}]
    _, entities = extract_from_scene_results(results)
    names = {e.name for e in entities if e.kind == "character"}
    assert "Mary" not in names  # only 1 mention
    assert "Ganesh" not in names  # 2 mentions, still below threshold of 3


def test_empty_input_returns_empty():
    assert extract_from_scene_results([]) == ([], [])


def test_results_with_no_usable_data():
    results = [{"result_data": {"raw_text": ""}}]
    cues, entities = extract_from_scene_results(results)
    assert cues == []
    assert entities == []


def test_merges_close_appearances():
    """Two appearances 3s apart should be merged; 30s apart should not."""
    results = [
        {
            "result_data": {
                "cues": [],
                "entities": [
                    {
                        "name": "X",
                        "kind": "character",
                        "appearances": [
                            {"start_sec": 10, "end_sec": 12},
                            {"start_sec": 14, "end_sec": 18},  # gap 2 → merge
                            {"start_sec": 50, "end_sec": 55},  # gap 32 → keep separate
                        ],
                    }
                ],
                "events": [],
            }
        }
    ]
    _, entities = extract_from_scene_results(results)
    assert entities[0].appearances == [(10.0, 18.0), (50.0, 55.0)]
