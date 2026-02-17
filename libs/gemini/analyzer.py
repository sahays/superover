"""
Gemini API analyzer for video content (legacy).
Uses the google-genai SDK with Vertex AI backend.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger(__name__)


def _model_name(name: str) -> str:
    """Strip 'models/' prefix if present."""
    return name.removeprefix("models/")


class GeminiAnalyzer:
    """Gemini-based video analysis."""

    def __init__(self):
        """Initialize google-genai client with Vertex AI backend."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_region,
        )
        self.model_name = _model_name(settings.gemini_default_model)

    def analyze_video_file(self, video_path: Path, analysis_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze a video file using Gemini."""
        if analysis_types is None:
            analysis_types = ["scene", "objects", "transcription", "moderation"]

        data = video_path.read_bytes()
        video_part = types.Part.from_bytes(data=data, mime_type="video/mp4")
        logger.info(f"Loaded video for Gemini analysis: {video_path.name}")

        results = {}
        if "scene" in analysis_types:
            results["scene_analysis"] = self._analyze_scene(video_part)
        if "objects" in analysis_types:
            results["object_detection"] = self._detect_objects(video_part)
        if "transcription" in analysis_types:
            results["transcription"] = self._transcribe(video_part)
        if "moderation" in analysis_types:
            results["moderation"] = self._moderate_content(video_part)
        return results

    def analyze_video_from_gcs(self, gcs_uri: str, analysis_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze a video from GCS URI directly."""
        if analysis_types is None:
            analysis_types = ["scene", "objects", "transcription", "moderation"]

        video_part = types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4")
        logger.info(f"Accessing video from GCS: {gcs_uri}")

        results = {}
        if "scene" in analysis_types:
            results["scene_analysis"] = self._analyze_scene(video_part)
        if "objects" in analysis_types:
            results["object_detection"] = self._detect_objects(video_part)
        if "transcription" in analysis_types:
            results["transcription"] = self._transcribe(video_part)
        if "moderation" in analysis_types:
            results["moderation"] = self._moderate_content(video_part)
        return results

    def _generate(self, prompt: str, media_part) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[prompt, media_part],
        )
        return response.text

    def _analyze_scene(self, video_part) -> Dict[str, Any]:
        prompt = """Analyze this video and provide a detailed scene-by-scene breakdown.
For each distinct scene, provide: timestamp range, description, key visual elements,
scene type/category, and notable events. Format as JSON."""
        return self._parse_json_response(self._generate(prompt, video_part))

    def _detect_objects(self, video_part) -> Dict[str, Any]:
        prompt = """Identify and track all significant objects, people, and entities in this video.
For each, provide: type, description, first appearance timestamp, appearances count,
and characteristics. Format as JSON."""
        return self._parse_json_response(self._generate(prompt, video_part))

    def _transcribe(self, video_part) -> Dict[str, Any]:
        prompt = """Transcribe all speech and audio in this video with timestamps,
speaker identification, and subtitle-formatted output. Format as JSON."""
        return self._parse_json_response(self._generate(prompt, video_part))

    def _moderate_content(self, video_part) -> Dict[str, Any]:
        prompt = """Analyze this video for content moderation: violence, adult content,
hate speech, dangerous activities, sensitive topics. Rate severity and provide
timestamps. Format as JSON."""
        return self._parse_json_response(self._generate(prompt, video_part))

    @staticmethod
    def _parse_json_response(response_text: str) -> Dict[str, Any]:
        try:
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
            return {"error": "Failed to parse response", "raw_response": response_text}


_analyzer_instance: Optional[GeminiAnalyzer] = None


def get_analyzer() -> GeminiAnalyzer:
    """Get or create Gemini analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = GeminiAnalyzer()
    return _analyzer_instance
