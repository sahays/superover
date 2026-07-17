"""Unit tests for the event model + JSON I/O (libs/basketball/timeline.py)."""

import json

import pytest

from libs.basketball.timeline import (
    Event,
    events_from_json,
    events_to_json,
    predictions_from_dict,
    predictions_to_dict,
    read_predictions,
    write_predictions,
)

pytestmark = pytest.mark.unit


def full_event() -> Event:
    return Event(
        t=12.5,
        t_end=14.0,
        type="shot",
        outcome="made",
        team="kansas",
        points=3,
        jersey="24",
        confidence={"overall": 0.92, "team": 0.85, "points": 0.99, "jersey": 0.6},
        evidence=["scorebug:delta+3@14.1", "shots:rim-through@12.6"],
    )


class TestEvent:
    def test_dict_round_trip(self):
        event = full_event()
        assert Event.from_dict(event.to_dict()) == event

    def test_json_round_trip(self):
        event = full_event()
        assert Event.from_json(event.to_json()) == event

    def test_minimal_event(self):
        event = Event.from_dict({"t": 3.0, "type": "score_change"})
        assert event.t_end is None
        assert event.outcome is None
        assert event.confidence == {}
        assert event.evidence == []

    def test_midpoint(self):
        assert Event(t=10.0, type="shot").midpoint == 10.0
        assert Event(t=10.0, t_end=20.0, type="shot").midpoint == 15.0

    def test_jersey_coerced_to_str(self):
        assert Event.from_dict({"t": 1.0, "type": "shot", "jersey": 24}).jersey == "24"

    def test_unknown_field_rejected(self):
        with pytest.raises(ValueError, match="Unknown Event fields"):
            Event.from_dict({"t": 1.0, "type": "shot", "bogus": 1})

    def test_required_fields(self):
        with pytest.raises(ValueError):
            Event.from_dict({"type": "shot"})


class TestEventListJson:
    def test_round_trip(self):
        events = [full_event(), Event(t=20.0, type="free_throw", outcome="missed")]
        assert events_from_json(events_to_json(events)) == events

    def test_non_list_rejected(self):
        with pytest.raises(ValueError):
            events_from_json('{"t": 1.0}')


class TestPredictionsFile:
    def test_format(self):
        data = predictions_to_dict("shot_0013-1a2b3c4d", [full_event()])
        assert data["clip_id"] == "shot_0013-1a2b3c4d"
        assert isinstance(data["events"], list)
        assert data["events"][0]["type"] == "shot"

    def test_file_round_trip(self, tmp_path):
        events = [full_event()]
        path = tmp_path / "pred.json"
        write_predictions(path, "shot_0013-1a2b3c4d", events)
        clip_id, loaded = read_predictions(path)
        assert clip_id == "shot_0013-1a2b3c4d"
        assert loaded == events
        # file is plain JSON with exactly the documented keys
        raw = json.loads(path.read_text())
        assert set(raw) == {"clip_id", "events"}

    def test_missing_keys_rejected(self):
        with pytest.raises(ValueError):
            predictions_from_dict({"events": []})
        with pytest.raises(ValueError):
            predictions_from_dict({"clip_id": "x"})
