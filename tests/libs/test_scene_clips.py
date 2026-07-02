"""Unit tests for libs/scene_clips.py — scene-entry projection for clip indexing."""

import pytest

from libs.scene_clips import build_scene_text, extract_scene_entries

pytestmark = pytest.mark.unit


class TestSceneSchema:
    def test_extracts_timed_scenes_and_drops_untimed(self):
        rd = {
            "scenes": [
                {
                    "start_time": "00:01:10.500",
                    "end_time": "00:01:42.000",
                    "summary": "Chase across the rooftop",
                    "people": [{"label": "Bob Biswas"}, {"label": "Person 2"}],
                },
                {"summary": "no times"},
                {"start_time": "00:02:00", "end_time": "00:02:00", "summary": "zero-length"},
            ]
        }
        entries = extract_scene_entries(rd)
        assert len(entries) == 1
        assert entries[0]["start"] == "00:01:10"
        assert entries[0]["end"] == "00:01:42"
        assert entries[0]["people"] == ["Bob Biswas"]  # generic "Person N" dropped

    def test_caps_scene_count(self):
        rd = {
            "scenes": [
                {"start_time": f"00:00:{i:02d}", "end_time": f"00:01:{i:02d}", "summary": f"s{i}"} for i in range(20)
            ]
        }
        assert len(extract_scene_entries(rd)) == 12


class TestEventSchema:
    def test_converts_seconds_and_prefixes_tag(self):
        rd = {"events": [{"start_sec": 65.4, "end_sec": 92.0, "description": "free kick scored", "tag": "goal"}]}
        entries = extract_scene_entries(rd)
        assert entries[0]["start"] == "00:01:05"
        assert entries[0]["end"] == "00:01:32"
        assert entries[0]["summary"] == "goal: free kick scored"

    def test_no_scenes_or_events(self):
        assert extract_scene_entries({}) == []
        assert extract_scene_entries({"scenes": [], "events": []}) == []


class TestBuildSceneText:
    def test_includes_classification_summary_and_people(self):
        text = build_scene_text(
            {"summary": "Chase across the rooftop", "people": ["Bob Biswas"]},
            {"genre": "Thriller", "type": "movie"},
        )
        assert text == "Genre: Thriller Type: movie Chase across the rooftop People: Bob Biswas"
