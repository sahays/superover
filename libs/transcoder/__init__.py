"""Transcoder API integration for media processing."""

from functools import lru_cache
from .client import TranscoderClient

__all__ = ["TranscoderClient", "get_transcoder_client"]


@lru_cache()
def get_transcoder_client() -> TranscoderClient:
    """Get a singleton Transcoder client instance."""
    return TranscoderClient()
