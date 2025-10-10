"""
Gemini Scene Analyzer
Provides detailed video analysis including objects, emotions, dialogues, moderation, etc.
"""
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)


class SceneAnalyzer:
    """Analyzes video scenes using Gemini with detailed prompts."""

    def __init__(self):
        """Initialize Gemini API."""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def analyze_chunk(
        self,
        video_path: Path,
        chunk_index: int,
        chunk_duration: float,
        prompt_text: str,
    ) -> Dict[str, Any]:
        """
        Analyze a video chunk with comprehensive scene analysis.

        Args:
            video_path: Path to the video chunk file
            chunk_index: Index of this chunk in the full video
            chunk_duration: Duration of the chunk in seconds
            prompt_text: The full prompt text to use for the analysis.

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

            # Generate analysis
            response = self.model.generate_content(
                [prompt_text, video_file],
                generation_config=genai.GenerationConfig(
                    temperature=0.1,  # Low temperature for more consistent/factual output
                    max_output_tokens=8192,  # Allow long detailed responses
                )
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

            # Parse JSON response
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```json")[-1].split("```")[0].strip()
            elif response_text.startswith("```"):
                response_text = response_text.split("```")[1].strip()

            result = json.loads(response_text)

            # Add metadata
            result["chunk_index"] = chunk_index
            result["chunk_duration"] = chunk_duration
            result["gemini_file_uri"] = video_file.uri

            logger.info(f"Successfully analyzed chunk {chunk_index}")

            # Clean up uploaded file
            try:
                genai.delete_file(video_file.name)
                logger.info(f"Deleted uploaded file for chunk {chunk_index}")
            except Exception as e:
                logger.warning(f"Failed to delete uploaded file: {e}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")

        except Exception as e:
            logger.error(f"Error analyzing chunk {chunk_index}: {e}")
            raise

