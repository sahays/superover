"""Tests for libs/content_owner.py (filename -> studio owner derivation)."""

import pytest

from libs.content_owner import derive_owner_from_filename


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("sony-super-over.mp4", "sony"),
        ("SONY_Highlights.MP4", "sony"),  # case-insensitive
        ("clip-from-sony.mov", "sony"),  # substring anywhere
        ("zee-match.mp4", "zee"),
        ("Zee5_episode.mp4", "zee"),  # zee5 marker maps to zee
        ("random-clip.mp4", ""),  # no marker -> untagged (shared)
        ("", ""),  # empty filename
    ],
)
def test_derive_owner_from_filename(filename, expected):
    assert derive_owner_from_filename(filename) == expected


def test_first_match_wins(monkeypatch):
    """When multiple slugs could match, config insertion order decides."""
    from config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "content_owners", {"sony": ["x"], "zee": ["x"]})
    assert derive_owner_from_filename("clip-x.mp4") == "sony"
