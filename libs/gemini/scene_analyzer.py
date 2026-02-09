"""
Gemini Scene Analyzer
Provides detailed video analysis including objects, emotions, dialogues, moderation, etc.
"""
import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, Field
from config import settings

logger = logging.getLogger(__name__)

class SceneAnalysisResponse(BaseModel):
    """Schema for scene analysis results."""
    summary: str = Field(description="High-level summary of the scene")
    objects: List[str] = Field(description="List of significant objects detected")
    emotions: List[str] = Field(description="List of emotions detected in the scene")
    transcription: Optional[str] = Field(None, description="Transcription of any spoken dialogue")
    moderation_tags: List[str] = Field(description="Safety or moderation tags")

class SceneAnalyzer:
    """Analyzes video scenes using Gemini with detailed prompts."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        """Initialize Gemini API."""
        genai.configure(api_key=settings.gemini_api_key)
        
        # Configure model with structured output schema
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_default_model,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": SceneAnalysisResponse,
            }
        )
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute a function with exponential backoff retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function

        Raises:
            Exception: The last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (google_exceptions.DeadlineExceeded, google_exceptions.ServiceUnavailable) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Calculate delay with exponential backoff
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed with {type(e).__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} retry attempts failed")
            except Exception as e:
                # For non-retryable errors, fail immediately
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                raise

        # If we get here, all retries failed
        raise last_exception

    def _calculate_cost(self, usage_metadata) -> Dict[str, Any]:
        """
        Calculate cost based on token usage and model pricing.
        
        Pricing (as of Nov 2025):
        Gemini 3.0 Pro Preview:
          Input: $2.00/1M (<=200k), $4.00/1M (>200k)
          Output: $12.00/1M (<=200k), $18.00/1M (>200k)
        
        Gemini 2.5 Pro:
          Input: $1.25/1M (<=128k), $2.50/1M (>128k)
          Output: $5.00/1M (<=128k), $10.00/1M (>128k)

        Gemini 2.0 Flash:
          Input: $0.10/1M
          Output: $0.40/1M
        """
        if not usage_metadata:
            return {}

        prompt_tokens = usage_metadata.prompt_token_count
        candidates_tokens = usage_metadata.candidates_token_count
        total_tokens = usage_metadata.total_token_count
        
        model_name = settings.gemini_default_model.lower()
        input_rate = 0.0
        output_rate = 0.0

        if "gemini-3" in model_name: # Gemini 3.0 Pro Preview
            # Input cost
            if prompt_tokens <= 200000:
                input_rate = 2.00
            else:
                input_rate = 4.00
            
            # Output cost
            if prompt_tokens <= 200000:
                output_rate = 12.00
            else:
                output_rate = 18.00
                
        elif "gemini-2.5" in model_name or "gemini-pro" in model_name: # Gemini 2.5 Pro
            # Input cost
            if prompt_tokens <= 128000:
                input_rate = 1.25
            else:
                input_rate = 2.50
            
            # Output cost
            if prompt_tokens <= 128000:
                output_rate = 5.00
            else:
                output_rate = 10.00

        elif "flash" in model_name: # Flash models (cheap)
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
            "estimated_cost_usd": round(cost, 6)
        }

    def analyze_chunk(
        self,
        media_path: Path,
        chunk_index: int,
        chunk_duration: float,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
        context_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a media chunk (video or audio) with comprehensive analysis.

        Args:
            media_path: Path to the media chunk file
            chunk_index: Index of this chunk in the full file
            chunk_duration: Duration of the chunk in seconds
            prompt_text: The full prompt text to use for the analysis.
            prompt_type: Type of analysis (scene_analysis, subtitling, etc.)
            context_text: Optional pre-loaded context text to append to prompt

        Returns:
            Comprehensive analysis results as a dictionary
        """
        try:
            logger.info(f"Uploading chunk {chunk_index} to Gemini: {media_path.name}")

            # Upload media file to Gemini
            media_file = genai.upload_file(str(media_path))

            # Wait for processing
            logger.info(f"Waiting for Gemini to process chunk {chunk_index}")
            while media_file.state.name == "PROCESSING":
                import time
                time.sleep(2)
                media_file = genai.get_file(media_file.name)

            if media_file.state.name == "FAILED":
                raise ValueError(f"Gemini processing failed for chunk {chunk_index}")

            logger.info(f"Analyzing chunk {chunk_index} with Gemini")

            # Use max output tokens from config (model-specific)
            # Gemini 2.0 Flash: 8192 tokens
            # Gemini 2.5 Pro: 65536 tokens
            max_tokens = settings.gemini_default_output_tokens
            logger.info(f"Using max_output_tokens={max_tokens} for model {settings.gemini_default_model}")

            # Build content parts: prompt + context (if any) + media
            content_parts = []

            # Add prompt text (with context appended if provided)
            if context_text:
                # Append pre-loaded context to prompt
                full_prompt = prompt_text + "\n\n" + context_text
                content_parts.append(full_prompt)
                logger.info(f"Including context ({len(context_text)} chars) in analysis")
            else:
                content_parts.append(prompt_text)

            # Add media file
            content_parts.append(media_file)

            # Generate analysis with extended timeout for media processing
            response = self._retry_with_backoff(
                self.model.generate_content,
                content_parts,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=SceneAnalysisResponse
                ),
                request_options={"timeout": 600}
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
                    "chunk_duration": chunk_duration
                }

            # Parse response
            try:
                result = json.loads(response.text)
                result["finish_reason"] = str(response.candidates[0].finish_reason)
                logger.info(f"Successfully analyzed chunk {chunk_index}")
            except Exception as e:
                logger.warning(f"Failed to parse structured output: {e}")
                result = {
                    "raw_response": response.text, 
                    "parse_error": str(e),
                    "finish_reason": str(response.candidates[0].finish_reason)
                }

            # Calculate cost and usage
            if hasattr(response, "usage_metadata"):
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
            result["gemini_file_uri"] = media_file.uri

            # Clean up uploaded file
            try:
                genai.delete_file(media_file.name)
                logger.info(f"Deleted uploaded file for chunk {chunk_index}")
            except Exception as e:
                logger.warning(f"Failed to delete uploaded file: {e}")

            return result

        except Exception as e:
            logger.error(f"Error analyzing chunk {chunk_index}: {e}")
            raise

