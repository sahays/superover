"""
Gemini Scene Analyzer
Provides detailed video analysis using the google-genai SDK with Vertex AI.
Authentication via ADC — no API key needed on Cloud Run.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from config import settings
from libs.gemini.common import model_name, retry_with_backoff, calculate_cost

logger = logging.getLogger(__name__)


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
        self.model_name = model_name(settings.gemini_default_model)
        self.max_retries = max_retries
        self.base_delay = base_delay

    def analyze_chunk(
        self,
        media_path: Optional[Path],
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
            media_path: Path to the media chunk file (fallback if no gcs_path, can be None)
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
                "temperature": settings.gemini_temperature,
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

            # Generate analysis with continuation loop for truncated responses
            max_continuations = 5
            accumulated_text = ""
            continuation_count = 0
            total_usage_stats = {}
            final_finish_reason = "UNKNOWN"

            for iteration in range(max_continuations + 1):
                if iteration == 0:
                    call_contents = contents
                else:
                    # Continuation: send original prompt + media + accumulated text so far
                    continuation_prompt = (
                        f"Continue exactly where you left off. "
                        f"Here is what you have generated so far:\n\n{accumulated_text}\n\n"
                        f"Continue from the exact point where this was cut off. "
                        f"Do not repeat any content already generated."
                    )
                    call_contents = contents + [continuation_prompt]
                    logger.info(
                        f"Chunk {chunk_index}: continuation {continuation_count + 1}, "
                        f"accumulated {len(accumulated_text)} chars so far"
                    )

                response = retry_with_backoff(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=call_contents,
                    config=types.GenerateContentConfig(**gen_config_kwargs),
                    max_retries=self.max_retries,
                    base_delay=self.base_delay,
                )

                # Check if response was blocked
                if not response.candidates or not response.candidates[0].content.parts:
                    finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                    if iteration == 0:
                        logger.warning(
                            f"Gemini response blocked for chunk {chunk_index}. Finish reason: {finish_reason}"
                        )
                        return {
                            "summary": f"Analysis blocked (reason: {finish_reason})",
                            "blocked": True,
                            "finish_reason": str(finish_reason),
                            "chunk_index": chunk_index,
                            "chunk_duration": chunk_duration,
                        }
                    else:
                        logger.warning(f"Continuation {continuation_count + 1} blocked for chunk {chunk_index}")
                        break

                # Accumulate token usage across continuations
                if response.usage_metadata:
                    iter_usage = calculate_cost(response.usage_metadata, settings.gemini_default_model)
                    if not total_usage_stats:
                        total_usage_stats = iter_usage.copy()
                    else:
                        for key in ["prompt_tokens", "candidates_tokens", "total_tokens"]:
                            total_usage_stats[key] = total_usage_stats.get(key, 0) + iter_usage.get(key, 0)
                        for key in ["input_cost_usd", "output_cost_usd", "estimated_cost_usd"]:
                            total_usage_stats[key] = round(total_usage_stats.get(key, 0) + iter_usage.get(key, 0), 6)

                accumulated_text += response.text
                final_finish_reason = str(response.candidates[0].finish_reason)

                # Check if response is complete
                if final_finish_reason != "MAX_TOKENS":
                    if iteration > 0:
                        logger.info(
                            f"Chunk {chunk_index}: completed after {continuation_count + 1} continuation(s), "
                            f"total {len(accumulated_text)} chars"
                        )
                    break

                continuation_count += 1
                logger.warning(
                    f"Chunk {chunk_index}: response truncated (MAX_TOKENS) at iteration {iteration + 1}, "
                    f"{len(accumulated_text)} chars so far. Continuing..."
                )

            # Parse the accumulated response
            if response_schema is not None:
                try:
                    result = json.loads(accumulated_text)
                    result["finish_reason"] = final_finish_reason
                    logger.info(f"Successfully analyzed chunk {chunk_index} (structured)")
                except Exception as e:
                    logger.warning(f"Failed to parse structured output: {e}")
                    result = {
                        "raw_response": accumulated_text,
                        "parse_error": str(e),
                        "finish_reason": final_finish_reason,
                    }
            else:
                result = {
                    "raw_text": accumulated_text,
                    "finish_reason": final_finish_reason,
                }
                logger.info(f"Successfully analyzed chunk {chunk_index} (free text)")

            if continuation_count > 0:
                result["continuation_count"] = continuation_count
            if final_finish_reason == "MAX_TOKENS":
                result["is_truncated"] = True

            # Calculate cost and usage (aggregated across all continuations)
            if total_usage_stats:
                result["token_usage"] = total_usage_stats
                logger.info(
                    f"Chunk {chunk_index} total usage: "
                    f"Prompt={total_usage_stats.get('prompt_tokens', 0)}, "
                    f"Output={total_usage_stats.get('candidates_tokens', 0)}, "
                    f"Total={total_usage_stats.get('total_tokens', 0)} | "
                    f"Cost=${total_usage_stats.get('estimated_cost_usd', 0):.6f}"
                    + (f" (across {continuation_count + 1} calls)" if continuation_count > 0 else "")
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
