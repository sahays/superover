"""Gemini Search Query Interpreter — translates multilingual/multimodal input to English BQ query."""

import json
import logging
import time

from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from config import settings

logger = logging.getLogger(__name__)

INTERPRETER_SYSTEM_PROMPT = """\
You are a search query translator. Given user input (text in any language, \
or audio, or both), output a concise English search query suitable for \
semantic vector search against video analysis content.

Rules:
- Translate the user's intent into a short, natural English search phrase.
- Focus on the key concepts: people, actions, objects, moods, genres, settings.
- Strip filler words and keep the query concise (under 20 words).
- If the input is audio, transcribe and translate to English.
- If both text and audio are provided, combine the intent from both.
- Output ONLY the search query fields, nothing else.
"""

RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "english_query": types.Schema(
            type=types.Type.STRING,
            description="Concise English search query",
        ),
        "detected_language": types.Schema(
            type=types.Type.STRING,
            description="Detected input language (e.g. 'en', 'hi', 'es')",
        ),
    },
    required=["english_query", "detected_language"],
)


def _model_name(name: str) -> str:
    """Strip 'models/' prefix if present."""
    return name.removeprefix("models/")


def _is_simple_english(text: str) -> bool:
    """Check if text is ASCII-only and looks like simple English.

    Returns True for basic English queries that don't need interpretation.
    """
    if not text or not text.strip():
        return False
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


class SearchQueryInterpreter:
    """Interprets multimodal/multilingual search input into an English BQ query."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = _model_name(settings.gemini_search_model)
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute a function with exponential backoff retry logic."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ServiceUnavailable,
            ) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} retry attempts failed")
            except Exception as e:
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                raise

        raise last_exception

    def interpret_query(
        self,
        text: str | None = None,
        audio_bytes: bytes | None = None,
        audio_mime: str | None = None,
    ) -> str:
        """Interpret multimodal/multilingual input into an English search query.

        Fast-path: if text is simple ASCII English and no audio, return as-is.
        Otherwise, calls Gemini Flash Lite for interpretation.

        Returns the English search query string.
        """
        # Fast path: simple English text, no audio
        if text and not audio_bytes and _is_simple_english(text):
            logger.info(f"Fast path: simple English query '{text}'")
            return text.strip()

        # Build multimodal content parts
        contents = []

        if text:
            contents.append(types.Part.from_text(text=f"Text input: {text}"))

        if audio_bytes and audio_mime:
            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=audio_mime))

        if not contents:
            raise ValueError("Either text or audio must be provided")

        try:
            response = self._retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=INTERPRETER_SYSTEM_PROMPT,
                    max_output_tokens=256,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=0,
                    ),
                ),
            )

            result = json.loads(response.text)
            english_query = result.get("english_query", "").strip()
            detected_lang = result.get("detected_language", "unknown")

            logger.info(f"Query interpreted: '{text}' [{detected_lang}] -> '{english_query}'")
            return english_query or (text or "").strip()

        except Exception as e:
            logger.error(f"Query interpretation failed: {e}", exc_info=True)
            # Fallback: return original text if available
            if text:
                return text.strip()
            raise
