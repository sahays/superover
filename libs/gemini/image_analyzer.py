"""
Gemini Image Analyzer
Provides generative image adaptation using the google-genai SDK with Vertex AI.
Authentication via ADC — no API key needed on Cloud Run.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from google import genai
from google.genai import types
from config import settings
from libs.gemini.common import model_name, retry_with_backoff, calculate_cost

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Generates image adaptations using Gemini via the google-genai SDK."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        """Initialize google-genai client with Vertex AI backend."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = model_name(settings.gemini_image_model)
        self.max_retries = max_retries
        self.base_delay = base_delay

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

            response = retry_with_backoff(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[full_prompt, image_part],
                config=types.GenerateContentConfig(
                    max_output_tokens=settings.gemini_image_output_tokens,
                    temperature=settings.gemini_temperature,
                ),
                max_retries=self.max_retries,
                base_delay=self.base_delay,
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
                usage_stats = calculate_cost(response.usage_metadata, settings.gemini_image_model)

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
