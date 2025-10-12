"""
Gemini Scene Analyzer
Provides detailed video analysis including objects, emotions, dialogues, moderation, etc.
"""
import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from config import settings

logger = logging.getLogger(__name__)


class SceneAnalyzer:
    """Analyzes video scenes using Gemini with detailed prompts."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        """Initialize Gemini API.

        Args:
            max_retries: Maximum number of retry attempts for API calls
            base_delay: Base delay in seconds for exponential backoff
        """
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
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

    def analyze_chunk(
        self,
        video_path: Path,
        chunk_index: int,
        chunk_duration: float,
        prompt_text: str,
        prompt_type: str = "scene_analysis",
    ) -> Dict[str, Any]:
        """
        Analyze a video chunk with comprehensive scene analysis.

        Args:
            video_path: Path to the video chunk file
            chunk_index: Index of this chunk in the full video
            chunk_duration: Duration of the chunk in seconds
            prompt_text: The full prompt text to use for the analysis.
            prompt_type: Type of analysis (scene_analysis, subtitling, etc.)

        Returns:
            Comprehensive analysis results as a dictionary
        """
        try:
            logger.info(f"Uploading chunk {chunk_index} to Gemini: {video_path.name}")

            # Upload video file to Gemini
            video_file = genai.upload_file(str(video_path))

            # Wait for processing
            logger.info(f"Waiting for Gemini to process chunk {chunk_index}")
            while video_file.state.name == "PROCESSING":
                import time
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                raise ValueError(f"Gemini processing failed for chunk {chunk_index}")

            logger.info(f"Analyzing chunk {chunk_index} with Gemini")

            # Determine max output tokens based on prompt type
            # Subtitling/transcription needs much more tokens for long SRT output
            if prompt_type in ["subtitling", "transcription"]:
                max_tokens = 65536  # Maximum for Gemini (65k tokens ~= 50k words)
                logger.info(f"Using max_output_tokens={max_tokens} for {prompt_type}")
            else:
                max_tokens = 8192  # Standard for scene analysis

            # Generate analysis with extended timeout for video processing
            # Use retry logic to handle transient failures
            response = self._retry_with_backoff(
                self.model.generate_content,
                [prompt_text, video_file],
                generation_config=genai.GenerationConfig(
                    temperature=0.1,  # Low temperature for more consistent/factual output
                    max_output_tokens=max_tokens,
                ),
                request_options={"timeout": 600}  # 10 minute timeout for video analysis
            )

            # Check if response was blocked
            if not response.candidates or not response.candidates[0].content.parts:
                # Response was blocked (safety, etc.)
                finish_reason = response.candidates[0].finish_reason if response.candidates else None
                safety_ratings = response.candidates[0].safety_ratings if response.candidates else None

                logger.warning(f"Gemini response blocked for chunk {chunk_index}. Finish reason: {finish_reason}")
                logger.warning(f"Safety ratings: {safety_ratings}")

                # Return a fallback response indicating the block
                result = {
                    "summary": f"Analysis blocked by content filter (finish_reason: {finish_reason})",
                    "blocked": True,
                    "finish_reason": str(finish_reason),
                    "safety_ratings": [
                        {
                            "category": str(rating.category),
                            "probability": str(rating.probability)
                        } for rating in (safety_ratings or [])
                    ],
                    "chunk_index": chunk_index,
                    "chunk_duration": chunk_duration,
                    "gemini_file_uri": video_file.uri
                }

                # Clean up uploaded file
                try:
                    genai.delete_file(video_file.name)
                    logger.info(f"Deleted uploaded file for chunk {chunk_index}")
                except Exception as e:
                    logger.warning(f"Failed to delete file for chunk {chunk_index}: {e}")

                return result

            # Parse response based on prompt type
            response_text = response.text.strip()

            # Handle different output formats based on prompt_type
            if prompt_type in ["subtitling", "transcription"]:
                # For subtitling/transcription, response may be SRT or plain text
                # Wrap in a JSON structure for consistent storage
                result = {
                    "subtitle_text": response_text,
                    "format": "srt" if "\n\n" in response_text and "-->" in response_text else "text",
                    "prompt_type": prompt_type
                }
                logger.info(f"Successfully analyzed chunk {chunk_index} as {prompt_type}")
            else:
                # For scene_analysis and other types, expect JSON
                # Remove markdown code blocks if present
                if response_text.startswith("```"):
                    response_text = response_text.split("```json")[-1].split("```")[0].strip()
                elif response_text.startswith("```"):
                    response_text = response_text.split("```")[1].strip()

                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError as e:
                    # If JSON parsing fails but response exists, wrap it
                    logger.warning(f"Failed to parse as JSON for prompt_type={prompt_type}, wrapping raw response")
                    result = {
                        "raw_response": response_text,
                        "parse_error": str(e),
                        "prompt_type": prompt_type
                    }

                logger.info(f"Successfully analyzed chunk {chunk_index}")

            # Add metadata
            result["chunk_index"] = chunk_index
            result["chunk_duration"] = chunk_duration
            result["gemini_file_uri"] = video_file.uri

            # Clean up uploaded file
            try:
                genai.delete_file(video_file.name)
                logger.info(f"Deleted uploaded file for chunk {chunk_index}")
            except Exception as e:
                logger.warning(f"Failed to delete uploaded file: {e}")

            return result

        except Exception as e:
            logger.error(f"Error analyzing chunk {chunk_index}: {e}")
            raise

