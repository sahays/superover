"""
Gemini API analyzer for video content.
Supports scene analysis, object detection, transcription, and moderation.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """Gemini-based video analysis."""

    def __init__(self):
        """Initialize Gemini API client."""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def analyze_video_file(
        self,
        video_path: Path,
        analysis_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a video file using Gemini.

        Args:
            video_path: Path to video file (local or GCS)
            analysis_types: List of analysis types to perform
                          ["scene", "objects", "transcription", "moderation"]
                          If None, performs all types

        Returns:
            Dictionary with analysis results
        """
        if analysis_types is None:
            analysis_types = ["scene", "objects", "transcription", "moderation"]

        # Upload video to Gemini
        video_file = genai.upload_file(str(video_path))
        logger.info(f"Uploaded video to Gemini: {video_file.name}")

        results = {}

        if "scene" in analysis_types:
            results["scene_analysis"] = self._analyze_scene(video_file)

        if "objects" in analysis_types:
            results["object_detection"] = self._detect_objects(video_file)

        if "transcription" in analysis_types:
            results["transcription"] = self._transcribe(video_file)

        if "moderation" in analysis_types:
            results["moderation"] = self._moderate_content(video_file)

        # Clean up
        video_file.delete()

        return results

    def analyze_video_from_gcs(
        self,
        gcs_uri: str,
        analysis_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a video from GCS URI directly.

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/video.mp4)
            analysis_types: List of analysis types

        Returns:
            Dictionary with analysis results
        """
        if analysis_types is None:
            analysis_types = ["scene", "objects", "transcription", "moderation"]

        # Gemini can access GCS files directly
        video_file = genai.get_file(name=gcs_uri)
        logger.info(f"Accessing video from GCS: {gcs_uri}")

        results = {}

        if "scene" in analysis_types:
            results["scene_analysis"] = self._analyze_scene(video_file)

        if "objects" in analysis_types:
            results["object_detection"] = self._detect_objects(video_file)

        if "transcription" in analysis_types:
            results["transcription"] = self._transcribe(video_file)

        if "moderation" in analysis_types:
            results["moderation"] = self._moderate_content(video_file)

        return results

    def _analyze_scene(self, video_file) -> Dict[str, Any]:
        """Analyze video scenes and describe what's happening."""
        prompt = """
        Analyze this video and provide a detailed scene-by-scene breakdown.
        For each distinct scene, provide:
        1. Timestamp range (start-end in seconds)
        2. Scene description (what is happening)
        3. Key visual elements
        4. Scene type/category (e.g., action, dialogue, transition)
        5. Notable events or changes

        Format the response as JSON with this structure:
        {
            "scenes": [
                {
                    "start_time": 0.0,
                    "end_time": 5.2,
                    "description": "...",
                    "visual_elements": ["..."],
                    "scene_type": "...",
                    "events": ["..."]
                }
            ],
            "summary": "Overall video summary"
        }
        """

        response = self.model.generate_content([prompt, video_file])
        return self._parse_json_response(response.text)

    def _detect_objects(self, video_file) -> Dict[str, Any]:
        """Detect and track objects throughout the video."""
        prompt = """
        Identify and track all significant objects, people, and entities in this video.
        For each detected object/entity, provide:
        1. Object type/category
        2. First appearance timestamp
        3. Frequency/duration of appearance
        4. Key characteristics or descriptions

        Format the response as JSON with this structure:
        {
            "objects": [
                {
                    "type": "person|object|animal|vehicle|other",
                    "description": "...",
                    "first_seen": 0.0,
                    "appearances": 5,
                    "total_duration": 30.5,
                    "characteristics": ["..."]
                }
            ]
        }
        """

        response = self.model.generate_content([prompt, video_file])
        return self._parse_json_response(response.text)

    def _transcribe(self, video_file) -> Dict[str, Any]:
        """Transcribe audio and generate subtitles."""
        prompt = """
        Transcribe all speech and audio in this video.
        Provide:
        1. Complete transcription with timestamps
        2. Speaker identification (if multiple speakers)
        3. Subtitle-formatted output

        Format the response as JSON with this structure:
        {
            "transcription": [
                {
                    "start_time": 0.0,
                    "end_time": 3.5,
                    "speaker": "Speaker 1",
                    "text": "...",
                    "confidence": 0.95
                }
            ],
            "subtitles": [
                {
                    "index": 1,
                    "start": "00:00:00,000",
                    "end": "00:00:03,500",
                    "text": "..."
                }
            ],
            "language": "en",
            "word_count": 150
        }
        """

        response = self.model.generate_content([prompt, video_file])
        return self._parse_json_response(response.text)

    def _moderate_content(self, video_file) -> Dict[str, Any]:
        """Check for inappropriate or sensitive content."""
        prompt = """
        Analyze this video for content moderation purposes.
        Check for:
        1. Violence or gore
        2. Adult/sexual content
        3. Hate speech or offensive language
        4. Dangerous activities
        5. Sensitive topics

        For each category, provide:
        - Present: yes/no
        - Severity: none|low|medium|high
        - Timestamps where found
        - Description of the content

        Format the response as JSON with this structure:
        {
            "safe_for_work": true,
            "age_rating": "G|PG|PG-13|R|NC-17",
            "categories": {
                "violence": {"present": false, "severity": "none", "instances": []},
                "adult_content": {"present": false, "severity": "none", "instances": []},
                "hate_speech": {"present": false, "severity": "none", "instances": []},
                "dangerous_activities": {"present": false, "severity": "none", "instances": []},
                "sensitive_topics": {"present": false, "severity": "none", "instances": []}
            },
            "warnings": [],
            "recommendation": "approve|review|reject"
        }
        """

        response = self.model.generate_content([prompt, video_file])
        return self._parse_json_response(response.text)

    @staticmethod
    def _parse_json_response(response_text: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response, handling markdown code blocks."""
        try:
            # Remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            return {"error": "Failed to parse response", "raw_response": response_text}


# Singleton instance
_analyzer_instance: Optional[GeminiAnalyzer] = None


def get_analyzer() -> GeminiAnalyzer:
    """Get or create Gemini analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = GeminiAnalyzer()
    return _analyzer_instance
