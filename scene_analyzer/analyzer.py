import os
import json
import time
import logging
import ffmpeg
import google.generativeai as genai
from dotenv import load_dotenv
from .models import SceneAnalysis, SceneAnalysisResult

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SceneAnalysisError(Exception):
    pass

GEMINI_PROMPT = """
You are an expert film and television scene analyst. Your task is to deconstruct the provided video and audio files into a structured JSON format. Analyze the content and generate a single JSON object with the following exact structure and fields:
{
  "start_timestamp_seconds": <float>,
  "end_timestamp_seconds": <float>,
  "summary": "<A concise, one-paragraph summary of the scene's plot and purpose.>",
  "setting": "<A detailed description of the environment, e.g., 'A dimly lit, modern office at night, with rain visible on the windows.'>",
  "emotional_tone": "<A single, descriptive term for the dominant emotion of the scene, e.g., 'Tense', 'Romantic', 'Action-Packed', 'Comedic'.>",
  "key_events": ["<A list of the most important actions or plot developments that occur in this scene.>"],
  "characters_present": ["<A list of all characters who are visibly present in the scene.>"],
  "dialogue_transcript": [
    {"character_name": "<Name of the character speaking>", "dialogue": "<The line of dialogue spoken>"},
    {"character_name": "<Next character>", "dialogue": "<Their line>"}
  ],
  "visible_objects": ["<A list of significant objects, vehicles, or symbols visible in the scene, e.g., 'Laptop', 'Red sports car', 'Golden key'>"],
  "camera_movement": "<A description of the camera work, e.g., 'Static shot', 'Slow pan from left to right', 'Handheld shaky cam'>",
  "sound_design": ["<A list of notable non-dialogue sounds, e.g., 'Distant siren', 'Ticking clock', 'Sudden gunshot'>"]
}
Provide only the raw JSON object as a response, with no additional text or formatting.
"""

def _get_file_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe['format']['duration'])
    except (ffmpeg.Error, KeyError):
        return 0.0

def analyze_scenes(manifest_file_path: str) -> dict:
    start_time = time.time()

    if not os.path.exists(manifest_file_path):
        raise FileNotFoundError(f"Manifest file not found: {manifest_file_path}")

    with open(manifest_file_path, 'r') as f:
        manifest = json.load(f)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SceneAnalysisError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

    video_files = [f['output_path'] for f in manifest.get('output_files', [])]
    if not video_files:
        raise SceneAnalysisError("No output files found in the manifest to analyze.")

    analyzed_scenes = []
    cumulative_time = 0.0

    for video_chunk_path in video_files:
        if not os.path.exists(video_chunk_path):
            logging.warning(f"Video file '{video_chunk_path}' from manifest not found. Skipping.")
            continue

        logging.info(f"Uploading video chunk: {video_chunk_path}")
        video_file = genai.upload_file(path=video_chunk_path)
        
        # Poll for the file to become ACTIVE
        while video_file.state.name == "PROCESSING":
            logging.info(f"Waiting for file '{video_file.name}' to be processed...")
            time.sleep(5)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name != "ACTIVE":
            raise SceneAnalysisError(f"File {video_file.name} failed to process. Final state: {video_file.state.name}")

        logging.info(f"File '{video_file.name}' is now ACTIVE. Sending to model for analysis.")
        
        try:
            response = model.generate_content([GEMINI_PROMPT, video_file])
            
            # Clean up the response text to extract the JSON
            response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            scene_data = json.loads(response_text)

            # Get timestamps
            duration = _get_file_duration(video_chunk_path)
            scene_data['start_timestamp_seconds'] = cumulative_time
            scene_data['end_timestamp_seconds'] = cumulative_time + duration
            cumulative_time += duration

            analyzed_scenes.append(SceneAnalysis(**scene_data))
            logging.info(f"Successfully analyzed and parsed scene for '{video_chunk_path}'.")

        except Exception as e:
            logging.error(f"Failed to analyze scene for '{video_chunk_path}': {e}")
            # Optionally, re-raise or continue
        finally:
            # Clean up uploaded file
            genai.delete_file(video_file.name)


    end_time = time.time()
    time_taken = round(end_time - start_time, 2)

    result = SceneAnalysisResult(
        source_manifest_path=manifest_file_path,
        analyzed_scenes=analyzed_scenes,
        status="success",
        message=f"Successfully analyzed {len(analyzed_scenes)} scenes.",
        time_taken_seconds=time_taken
    )

    return result.dict()
