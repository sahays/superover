"""
Gemini Image Analyzer
Provides generative image adaptation using Gemini 3 Pro Image Preview.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from config import settings

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Generates image adaptations using Gemini 3 Pro."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        """Initialize Gemini API."""
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_image_model)
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

        # Approximate pricing for Gemini 3 Pro Image Preview (Preview - subject to change)
        # Using placeholder rates similar to Pro Vision for now
        input_rate = 0.0025  # per 1k tokens (example)
        output_rate = 0.0050  # per 1k tokens (example)

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
        """
        Generate a single adapted image.
        """
        try:
            logger.info(f"Generating {target_ratio} adapt at {target_resolution}")

            # Construct the full prompt
            full_prompt = (
                f"Generate a high-quality image with aspect ratio {target_ratio} "
                f"and resolution {target_resolution}. "
                f"Instructions: {prompt_text}. "
                "Ensure professional composition and maintain the primary subject."
            )

            # Create image part from bytes
            image_part = {"mime_type": "image/jpeg", "data": image_bytes}

            # Call Gemini
            response = self._retry_with_backoff(
                self.model.generate_content,
                [full_prompt, image_part],
                generation_config=genai.GenerationConfig(
                    max_output_tokens=settings.gemini_image_output_tokens,
                    temperature=0.7,  # Creativity for generation
                ),
            )

            if not response.parts:
                return {
                    "error": "Blocked or empty response",
                    "stop_reason": str(response.candidates[0].finish_reason if response.candidates else "UNKNOWN"),
                }

            generated_image_bytes = None
            for part in response.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    generated_image_bytes = part.inline_data.data
                    break
                # Fallback check if the SDK exposes it differently
                if hasattr(part, "blob"):
                    generated_image_bytes = part.blob
                    break

            if not generated_image_bytes:
                # If no inline data, check for text (maybe it refused?)
                text_response = response.text if hasattr(response, "text") else "No text"
                logger.warning(f"No image data found in response. Text: {text_response}")
                return {
                    "error": "No image data returned",
                    "raw_text": text_response,
                    "stop_reason": str(response.candidates[0].finish_reason if response.candidates else "UNKNOWN"),
                }

            usage_stats = {}
            if hasattr(response, "usage_metadata"):
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
        """
        Generate multiple adapts in parallel.
        """
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
