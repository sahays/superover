"""
Gemini Scene Analyzer
Provides detailed video analysis using the google-genai SDK with Vertex AI.
Authentication via ADC — no API key needed on Cloud Run.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
from config import settings

logger = logging.getLogger(__name__)


def _model_name(name: str) -> str:
    """Strip 'models/' prefix if present."""
    return name.removeprefix("models/")


def _guess_mime_type(path: str) -> str:
    """Guess MIME type from file extension."""
    p = path.lower()
    if p.endswith(".mp3"):
        return "audio/mpeg"
    if p.endswith(".wav"):
        return "audio/wav"
    if p.endswith(".webm"):
        return "video/webm"
    return "video/mp4"


class SceneAnalyzer:
    """Analyzes video scenes using Gemini via the google-genai SDK."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        """Initialize google-genai client with Vertex AI backend."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = _model_name(settings.gemini_default_model)
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
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed with {type(e).__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} retry attempts failed")
            except Exception as e:
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                raise

        raise last_exception

    def _calculate_cost(self, usage_metadata) -> Dict[str, Any]:
        """Calculate cost based on token usage and model pricing."""
        if not usage_metadata:
            return {}

        prompt_tokens = usage_metadata.prompt_token_count
        candidates_tokens = usage_metadata.candidates_token_count
        total_tokens = usage_metadata.total_token_count

        model_name = settings.gemini_default_model.lower()
        input_rate = 0.0
        output_rate = 0.0

        if "gemini-3" in model_name:
            input_rate = 2.00 if prompt_tokens <= 200000 else 4.00
            output_rate = 12.00 if prompt_tokens <= 200000 else 18.00
        elif "gemini-2.5" in model_name or "gemini-pro" in model_name:
            input_rate = 1.25 if prompt_tokens <= 128000 else 2.50
            output_rate = 5.00 if prompt_tokens <= 128000 else 10.00
        elif "flash" in model_name:
            input_rate = 0.10
            output_rate = 0.40

        input_cost = (prompt_tokens / 1_000_000) * input_rate
        output_cost = (candidates_tokens / 1_000_000) * output_rate
        cost = input_cost + output_cost

        return {
            "prompt_tokens": prompt_tokens,
            "candidates_tokens": candidates_tokens,
            "total_tokens": total_tokens,
            "applied_input_rate": input_rate,
            "applied_output_rate": output_rate,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "estimated_cost_usd": round(cost, 6),
        }

    def analyze_chunk(
        self,
        media_path: Path,
        chunk_index: int,
        chunk_duration: float,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
        context_text: Optional[str] = None,
        gcs_path: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a media chunk (video or audio).

        Args:
            media_path: Path to the media chunk file (fallback if no gcs_path)
            chunk_index: Index of this chunk in the full file
            chunk_duration: Duration of the chunk in seconds
            prompt_text: The full prompt text to use for the analysis
            prompt_type: Type of analysis
            context_text: Optional context text to append to prompt
            gcs_path: Optional GCS URI — Vertex AI reads directly, no upload needed
            response_schema: Optional JSON schema for structured output.
                If provided, Gemini returns structured JSON matching this schema.
                If None, Gemini returns free text (no constraints).

        Returns:
            Analysis results as a dictionary
        """
        try:
            # Build content parts
            contents = []

            # Prompt (with context if provided)
            if context_text:
                contents.append(prompt_text + "\n\n" + context_text)
                logger.info(f"Including context ({len(context_text)} chars) in analysis")
            else:
                contents.append(prompt_text)

            # Media part — prefer GCS URI (no file upload needed)
            if gcs_path:
                mime_type = _guess_mime_type(gcs_path)
                contents.append(types.Part.from_uri(file_uri=gcs_path, mime_type=mime_type))
                logger.info(f"Using GCS URI for chunk {chunk_index}: {gcs_path}")
            else:
                mime_type = _guess_mime_type(str(media_path))
                data = media_path.read_bytes()
                contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
                logger.info(f"Using local file for chunk {chunk_index}: {media_path.name}")

            max_tokens = settings.gemini_default_output_tokens

            # Build generation config — structured output if schema provided, free text otherwise
            gen_config_kwargs = {
                "temperature": 0.1,
                "max_output_tokens": max_tokens,
            }
            if response_schema is not None:
                gen_config_kwargs["response_mime_type"] = "application/json"
                gen_config_kwargs["response_schema"] = response_schema
                logger.info(
                    f"Analyzing chunk {chunk_index} with {self.model_name} "
                    f"(structured output), max_output_tokens={max_tokens}"
                )
            else:
                logger.info(
                    f"Analyzing chunk {chunk_index} with {self.model_name} (free text), max_output_tokens={max_tokens}"
                )

            # Generate analysis
            response = self._retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(**gen_config_kwargs),
            )

            # Check if response was blocked
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                logger.warning(f"Gemini response blocked for chunk {chunk_index}. Finish reason: {finish_reason}")
                return {
                    "summary": f"Analysis blocked (reason: {finish_reason})",
                    "blocked": True,
                    "finish_reason": str(finish_reason),
                    "chunk_index": chunk_index,
                    "chunk_duration": chunk_duration,
                }

            # Parse response — structured JSON if schema was provided, free text otherwise
            if response_schema is not None:
                try:
                    result = json.loads(response.text)
                    result["finish_reason"] = str(response.candidates[0].finish_reason)
                    logger.info(f"Successfully analyzed chunk {chunk_index} (structured)")
                except Exception as e:
                    logger.warning(f"Failed to parse structured output: {e}")
                    result = {
                        "raw_response": response.text,
                        "parse_error": str(e),
                        "finish_reason": str(response.candidates[0].finish_reason),
                    }
            else:
                result = {
                    "raw_text": response.text,
                    "finish_reason": str(response.candidates[0].finish_reason),
                }
                logger.info(f"Successfully analyzed chunk {chunk_index} (free text)")

            # Calculate cost and usage
            if response.usage_metadata:
                usage_stats = self._calculate_cost(response.usage_metadata)
                result["token_usage"] = usage_stats
                logger.info(
                    f"Chunk {chunk_index} usage: "
                    f"Prompt={usage_stats.get('prompt_tokens', 0)}, "
                    f"Output={usage_stats.get('candidates_tokens', 0)}, "
                    f"Total={usage_stats.get('total_tokens', 0)} | "
                    f"Cost=${usage_stats.get('estimated_cost_usd', 0):.6f}"
                )

            # Add metadata
            result["chunk_index"] = chunk_index
            result["chunk_duration"] = chunk_duration
            if gcs_path:
                result["gcs_path"] = gcs_path

            return result

        except Exception as e:
            logger.error(f"Error analyzing chunk {chunk_index}: {e}")
            raise
