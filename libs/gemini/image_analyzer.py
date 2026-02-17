"""
Gemini Image Analyzer
Provides generative image adaptation using the google-genai SDK with Vertex AI.
Authentication via ADC — no API key needed on Cloud Run.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
from config import settings

logger = logging.getLogger(__name__)


def _model_name(name: str) -> str:
    """Strip 'models/' prefix if present."""
    return name.removeprefix("models/")


class ImageAnalyzer:
    """Generates image adaptations using Gemini via the google-genai SDK."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        """Initialize google-genai client with Vertex AI backend."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = _model_name(settings.gemini_image_model)
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
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    logger.error("All retry attempts failed")
            except Exception as e:
                logger.error(f"Non-retryable error: {e}")
                raise
        raise last_exception

    def _calculate_cost(self, usage_metadata) -> Dict[str, Any]:
        """Calculate cost based on token usage and model pricing."""
        if not usage_metadata:
            return {}

        prompt_tokens = usage_metadata.prompt_token_count
        candidates_tokens = usage_metadata.candidates_token_count

        input_rate = 0.0025  # per 1k tokens (placeholder)
        output_rate = 0.0050

        input_cost = (prompt_tokens / 1000) * input_rate
        output_cost = (candidates_tokens / 1000) * output_rate
        cost = input_cost + output_cost

        return {
            "input_tokens": prompt_tokens,
            "output_tokens": candidates_tokens,
            "estimated_cost_usd": round(cost, 6),
        }

    def generate_adapt(
        self,
        image_bytes: bytes,
        target_ratio: str,
        target_resolution: str,
        prompt_text: str,
    ) -> Dict[str, Any]:
        """Generate a single adapted image."""
        try:
            logger.info(f"Generating {target_ratio} adapt at {target_resolution}")

            full_prompt = (
                f"Generate a high-quality image with aspect ratio {target_ratio} "
                f"and resolution {target_resolution}. "
                f"Instructions: {prompt_text}. "
                "Ensure professional composition and maintain the primary subject."
            )

            image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

            response = self._retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[full_prompt, image_part],
                config=types.GenerateContentConfig(
                    max_output_tokens=settings.gemini_image_output_tokens,
                    temperature=0.7,
                ),
            )

            if not response.candidates or not response.candidates[0].content.parts:
                return {
                    "error": "Blocked or empty response",
                    "stop_reason": str(response.candidates[0].finish_reason if response.candidates else "UNKNOWN"),
                }

            generated_image_bytes = None
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    generated_image_bytes = part.inline_data.data
                    break

            if not generated_image_bytes:
                text_response = response.text if hasattr(response, "text") else "No text"
                logger.warning(f"No image data found in response. Text: {text_response}")
                return {
                    "error": "No image data returned",
                    "raw_text": text_response,
                    "stop_reason": str(response.candidates[0].finish_reason if response.candidates else "UNKNOWN"),
                }

            usage_stats = {}
            if response.usage_metadata:
                usage_stats = self._calculate_cost(response.usage_metadata)

            return {
                "image_bytes": generated_image_bytes,
                "usage": usage_stats,
                "stop_reason": str(response.candidates[0].finish_reason),
                "ratio": target_ratio,
            }

        except Exception as e:
            logger.error(f"Error generating adapt: {e}")
            return {"error": str(e), "stop_reason": "ERROR"}

    def generate_multiple_adapts(
        self,
        image_bytes: bytes,
        target_ratios: List[str],
        target_resolution: str,
        prompt_text: str,
    ) -> List[Dict[str, Any]]:
        """Generate multiple adapts in parallel."""
        results = []
        with ThreadPoolExecutor(max_workers=len(target_ratios)) as executor:
            future_to_ratio = {
                executor.submit(
                    self.generate_adapt,
                    image_bytes,
                    ratio,
                    target_resolution,
                    prompt_text,
                ): ratio
                for ratio in target_ratios
            }

            for future in as_completed(future_to_ratio):
                ratio = future_to_ratio[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Parallel generation failed for {ratio}: {e}")
                    results.append({"error": str(e), "ratio": ratio})

        return results


def get_image_analyzer() -> ImageAnalyzer:
    """Get or create ImageAnalyzer instance."""
    return ImageAnalyzer()
