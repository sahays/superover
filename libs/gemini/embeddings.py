"""Gemini text-embedding helper for the Bigtable search backend.

Unlike BigQuery's AI.EMBED (server-side, asynchronous), the Bigtable backend
generates embeddings explicitly — at sync time for documents and at query
time for searches. gemini-embedding-001 is multilingual, so raw Hindi/mixed
queries embed directly without the interpreter LLM.
"""

import logging
from functools import lru_cache

from google import genai
from google.genai import types

from config import settings
from libs.gemini.common import model_name, retry_with_backoff

logger = logging.getLogger(__name__)


class TextEmbedder:
    """Generates text embeddings via the Gemini embeddings API."""

    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            # Regional endpoint: measured ~0.2s vs 0.4-1.8s on "global".
            location=settings.embedding_region or settings.gcp_region,
        )
        self.model_name = model_name(settings.embedding_model)
        self.dimensions = settings.embedding_dimensions

    def embed(self, text: str, *, for_query: bool = False) -> list[float]:
        """Embed one text. `for_query` selects the retrieval task type."""
        task_type = "RETRIEVAL_QUERY" if for_query else "RETRIEVAL_DOCUMENT"
        response = retry_with_backoff(
            self.client.models.embed_content,
            model=self.model_name,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimensions,
            ),
        )
        values = list(response.embeddings[0].values)
        # gemini-embedding-001 returns unit-norm vectors only at the full 3072
        # dims; truncated outputs must be re-normalized.
        norm = sum(v * v for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        return values


@lru_cache(maxsize=1)
def get_text_embedder() -> TextEmbedder:
    """Get cached text embedder singleton."""
    return TextEmbedder()
