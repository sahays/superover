"""Gemini API integration."""

from functools import lru_cache
from .analyzer import GeminiAnalyzer
from .scene_analyzer import SceneAnalyzer
from .search_curator import SearchCurator
from .search_query_interpreter import SearchQueryInterpreter

__all__ = [
    "GeminiAnalyzer",
    "get_analyzer",
    "SceneAnalyzer",
    "get_scene_analyzer",
    "SearchCurator",
    "get_search_curator",
    "SearchQueryInterpreter",
    "get_search_query_interpreter",
]


@lru_cache()
def get_analyzer() -> GeminiAnalyzer:
    """Get a singleton Gemini analyzer instance."""
    return GeminiAnalyzer()


@lru_cache()
def get_scene_analyzer() -> SceneAnalyzer:
    """Get a singleton Scene analyzer instance."""
    return SceneAnalyzer()


@lru_cache()
def get_search_curator() -> SearchCurator:
    """Get a singleton Search curator instance."""
    return SearchCurator()


@lru_cache()
def get_search_query_interpreter() -> SearchQueryInterpreter:
    """Get a singleton Search query interpreter instance."""
    return SearchQueryInterpreter()
