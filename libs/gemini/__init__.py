"""Gemini API integration."""
from functools import lru_cache
from .analyzer import GeminiAnalyzer
from .scene_analyzer import SceneAnalyzer

__all__ = ["GeminiAnalyzer", "get_analyzer", "SceneAnalyzer", "get_scene_analyzer"]


@lru_cache()
def get_analyzer() -> GeminiAnalyzer:
    """Get a singleton Gemini analyzer instance."""
    return GeminiAnalyzer()


@lru_cache()
def get_scene_analyzer() -> SceneAnalyzer:
    """Get a singleton Scene analyzer instance."""
    return SceneAnalyzer()
