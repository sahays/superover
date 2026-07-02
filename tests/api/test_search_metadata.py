"""Unit tests for search.py metadata/embedding-text extraction of native
content_title/cast fields (emitted by the updated scene-analysis prompt)."""

import pytest

from api.routes.search import _build_embedding_text, _extract_metadata

pytestmark = pytest.mark.unit


class TestBuildEmbeddingText:
    def test_includes_native_title_and_cast_first(self):
        rd = {
            "content_title": "Sunflower",
            "cast": ["Sunil Grover", " Ranvir Shorey "],
            "genre": "Comedy",
            "chunk_summary": "hijinks in a housing society",
        }
        text = _build_embedding_text(rd)
        assert text.startswith("Title: Sunflower Cast: Sunil Grover, Ranvir Shorey")
        assert "Genre: Comedy" in text

    def test_ignores_empty_or_malformed_fields(self):
        rd = {"content_title": "  ", "cast": [None, "", 3], "genre": "Drama"}
        text = _build_embedding_text(rd)
        assert "Title:" not in text
        assert "Cast:" not in text


class TestExtractMetadata:
    def test_native_cast_wins_over_legacy_people(self):
        rd = {
            "cast": ["Sunil Grover"],
            "scenes": [{"people": [{"label": "Sonu"}]}],
        }
        assert _extract_metadata(rd)["actors"] == ["Sunil Grover"]

    def test_legacy_people_used_when_no_cast(self):
        rd = {"scenes": [{"people": [{"label": "Sonu"}, {"label": "Person 2"}]}]}
        assert _extract_metadata(rd)["actors"] == ["Sonu"]
