"""Tests for libs/engagement/scene_extract.py."""

import pytest

from libs.engagement.scene_extract import (
    extract_from_scene_results,
    extract_key_moments,
    extract_narrative_beats,
    extract_segments,
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


def test_structured_path_lifts_emotions_to_entities():
    """Time-bounded emotion segments become entities of kind='emotion' so the
    influence-delta logic and chip UI treat them like characters/events."""
    results = [
        {
            "result_data": {
                "cues": [],
                "entities": [],
                "events": [],
                "emotions": [
                    {"start_sec": 10.0, "end_sec": 20.0, "emotion": "tension", "intensity": 0.8},
                    {"start_sec": 12.0, "end_sec": 25.0, "emotion": "tension", "intensity": 0.6},  # merges with above
                    {"start_sec": 90.0, "end_sec": 110.0, "emotion": "romance", "intensity": 0.4},
                ],
            }
        },
    ]
    _, entities = extract_from_scene_results(results)
    by_name = {e.name: e for e in entities}
    assert by_name["tension"].kind == "emotion"
    assert by_name["tension"].mention_count == 2
    assert by_name["tension"].appearances == [(10.0, 25.0)]  # merged within 5s
    assert by_name["romance"].kind == "emotion"
    assert by_name["romance"].appearances == [(90.0, 110.0)]


def test_emotions_key_alone_triggers_structured_path():
    """A chunk carrying only `emotions` (no cues/entities/events) is structured."""
    results = [
        {
            "result_data": {
                "emotions": [
                    {"start_sec": 5.0, "end_sec": 8.0, "emotion": "joy", "intensity": 0.9},
                ],
            }
        },
    ]
    _, entities = extract_from_scene_results(results)
    assert len(entities) == 1
    assert entities[0].name == "joy"
    assert entities[0].kind == "emotion"


def test_emotion_and_event_intensity_averaged_onto_entity():
    """avg_intensity() averages the per-segment intensities for emotions/events."""
    results = [
        {
            "result_data": {
                "cues": [],
                "entities": [],
                "events": [
                    {"tag": "fight", "start_sec": 0.0, "end_sec": 5.0, "intensity": 0.8},
                    {"tag": "fight", "start_sec": 20.0, "end_sec": 25.0, "intensity": 0.4},
                ],
                "emotions": [
                    {"start_sec": 0.0, "end_sec": 5.0, "emotion": "tension", "intensity": 0.6},
                ],
            }
        },
    ]
    _, entities = extract_from_scene_results(results)
    by_name = {e.name: e for e in entities}
    assert by_name["fight"].avg_intensity() == pytest.approx(0.6)  # (0.8 + 0.4) / 2
    assert by_name["tension"].avg_intensity() == pytest.approx(0.6)


def test_cue_sentiment_is_threaded_through():
    results = [
        {
            "result_data": {
                "cues": [
                    {"start_sec": 1.0, "end_sec": 2.0, "text": "Yes!", "kind": "dialogue", "sentiment": "positive"},
                ],
                "entities": [],
                "events": [],
            }
        },
    ]
    cues, _ = extract_from_scene_results(results)
    assert cues[0].sentiment == "positive"


def test_extract_segments_sorted_across_chunks():
    results = [
        {"result_data": {"segments": [{"start_sec": 60.0, "end_sec": 90.0, "title": "B", "synopsis": "later"}]}},
        {
            "result_data": {
                "segments": [
                    {"start_sec": 0.0, "end_sec": 30.0, "title": "A", "synopsis": "early", "location": "palace"},
                ]
            }
        },
    ]
    segs = extract_segments(results)
    assert [s.title for s in segs] == ["A", "B"]
    assert segs[0].location == "palace"
    assert segs[1].location == ""  # default when omitted


def test_extract_key_moments_and_beats():
    results = [
        {
            "result_data": {
                "key_moments": [
                    {"start_sec": 120.0, "type": "cliffhanger", "label": "He turns around"},
                    {"start_sec": 10.0, "type": "hook", "label": "Cold open"},
                ],
                "narrative_beats": [
                    {"beat": "inciting_incident", "start_sec": 30.0, "end_sec": 40.0},
                ],
            }
        },
    ]
    moments = extract_key_moments(results)
    assert [m.type for m in moments] == ["hook", "cliffhanger"]  # sorted by start
    beats = extract_narrative_beats(results)
    assert beats[0].type == "inciting_incident"
    assert beats[0].label == "inciting incident"  # falls back to beat name


def test_segments_and_markers_empty_for_old_jobs():
    results = [{"result_data": {"cues": [], "entities": [], "events": []}}]
    assert extract_segments(results) == []
    assert extract_key_moments(results) == []
    assert extract_narrative_beats(results) == []


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
