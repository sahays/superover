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

    def get_comprehensive_prompt(self) -> str:
        """
        Get the comprehensive analysis prompt.

        This prompt instructs Gemini to analyze:
        - Objects and their timestamps
        - Camera movements
        - Emotions and expressions
        - Characters and their actions
        - Content moderation (violence, adult content, etc.)
        - Dialogues and speech
        """
        return """Analyze this video chunk comprehensively and provide a detailed JSON response with the following structure:

{
  "summary": "Brief 2-3 sentence summary of what happens in this chunk",
  "scene_description": "Detailed description of the overall scene setting and atmosphere",
  "objects": [
    {
      "name": "object name",
      "timestamp_start": "00:00:05",
      "timestamp_end": "00:00:12",
      "confidence": 0.95,
      "description": "detailed description of the object and its role in the scene"
    }
  ],
  "camera_movement": [
    {
      "type": "pan|zoom|tilt|static|tracking",
      "timestamp_start": "00:00:00",
      "timestamp_end": "00:00:08",
      "description": "description of camera movement and its effect"
    }
  ],
  "characters": [
    {
      "id": "unique identifier (e.g., person_1, character_name if known)",
      "description": "physical description",
      "first_appearance": "00:00:02",
      "last_appearance": "00:00:28",
      "actions": [
        {
          "timestamp": "00:00:05",
          "action": "description of what they're doing"
        }
      ],
      "emotions": [
        {
          "timestamp": "00:00:05",
          "emotion": "happy|sad|angry|surprised|neutral|fearful|disgusted",
          "intensity": "low|medium|high",
          "description": "context for the emotion"
        }
      ]
    }
  ],
  "dialogues": [
    {
      "timestamp": "00:00:05",
      "speaker": "character identifier or 'unknown'",
      "text": "transcribed dialogue or description if speech unclear",
      "language": "detected language",
      "confidence": 0.85
    }
  ],
  "audio_description": {
    "background_music": "description of music if present",
    "sound_effects": ["list of notable sound effects with brief descriptions"],
    "ambient_sounds": "description of background/ambient sounds"
  },
  "moderation": {
    "violence": {
      "detected": true|false,
      "severity": "none|low|medium|high",
      "timestamps": ["00:00:10", "00:00:15"],
      "description": "specific description of violent content if any"
    },
    "adult_content": {
      "detected": true|false,
      "severity": "none|low|medium|high",
      "description": "description if detected"
    },
    "profanity": {
      "detected": true|false,
      "instances": [
        {
          "timestamp": "00:00:12",
          "severity": "mild|moderate|severe"
        }
      ]
    },
    "sensitive_content": {
      "detected": true|false,
      "types": ["drug use", "weapons", "etc"],
      "description": "description of sensitive content"
    }
  },
  "scene_changes": [
    {
      "timestamp": "00:00:15",
      "type": "cut|fade|dissolve|wipe",
      "description": "what changes between scenes"
    }
  ],
  "visual_style": {
    "lighting": "bright|dark|natural|artificial|dramatic",
    "color_palette": "dominant colors and mood they create",
    "composition": "description of framing and visual composition"
  },
  "context_tags": ["action", "dialogue", "emotional", "informational", "etc"]
}

IMPORTANT INSTRUCTIONS:
1. All timestamps must be in MM:SS format relative to the chunk start (00:00)
2. Be as detailed and accurate as possible
3. If you cannot detect something with confidence, omit it or mark confidence as low
4. For moderation, err on the side of caution - flag anything potentially problematic
5. Transcribe dialogues verbatim when clear, describe when unclear
6. Identify emotions based on facial expressions, body language, and context
7. Return ONLY valid JSON, no additional text or markdown formatting
"""

    def analyze_chunk(
        self,
        video_path: Path,
        chunk_index: int,
        chunk_duration: float
    ) -> Dict[str, Any]:
        """
        Analyze a video chunk with comprehensive scene analysis.

        Args:
            video_path: Path to the video chunk file
            chunk_index: Index of this chunk in the full video
            chunk_duration: Duration of the chunk in seconds

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

            # Get the comprehensive prompt
            prompt = self.get_comprehensive_prompt()

            # Generate analysis
            response = self.model.generate_content(
                [prompt, video_file],
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

    def get_prompt_text(self) -> str:
        """Get the prompt text for storage in database."""
        return self.get_comprehensive_prompt()
