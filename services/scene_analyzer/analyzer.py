import os
import json
import time
import logging
import ffmpeg
import google.generativeai as genai
from dotenv import load_dotenv
from .models import SceneAnalysis
from common.storage import StorageManager

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SceneAnalysisError(Exception):
    pass

GEMINI_PROMPT = """
You are an expert film and television scene analyst. Your task is to deconstruct the provided video file into a structured JSON format. Analyze the content and generate a single JSON object with the following exact structure and fields. Timestamps must be in seconds relative to the start of the video file provided.

{
  "start_timestamp_seconds": 0.0,
  "end_timestamp_seconds": 0.0,
  "summary": "<A concise, one-paragraph summary of the scene's plot and purpose.>",
  "setting": "<A detailed description of the environment, e.g., 'A dimly lit, modern office at night, with rain visible on the windows.'>",
  "emotional_tone": "<A single, descriptive term for the dominant emotion of the scene, e.g., 'Tense', 'Romantic', 'Action-Packed', 'Comedic'.>",
  "key_events": [
    {"event": "<A key event or action>", "start_timestamp_seconds": 0.0}
  ],
  "characters_present": ["<A list of all characters who are visibly present in the scene.>"],
  "dialogue_transcript": [
    {"character_name": "<Name of the character speaking>", "dialogue": "<The line of dialogue spoken>", "detected_language": "<The detected language>", "start_timestamp_seconds": 0.0}
  ],
  "visible_objects": [
    {"object": "<A significant visible object>", "start_timestamp_seconds": 0.0}
  ],
  "camera_movement": "<A description of the camera work, e.g., 'Static shot', 'Slow pan from left to right', 'Handheld shaky cam'>",
  "sound_design": [
    {"sound": "<A notable non-dialogue sound>", "start_timestamp_seconds": 0.0}
  ],
  "moderation_flags": [
    {"flag": "<A content moderation flag, e.g., 'Violence'>", "start_timestamp_seconds": 0.0}
  ],
  "brand_recognition": [
    {"brand_name": "<The recognized brand>", "object_type": "<The object associated with the brand>", "description": "<A brief description of its appearance>", "start_timestamp_seconds": 0.0}
  ]
}
Provide only the raw JSON object as a response, with no additional text or formatting.
"""

def _get_file_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe['format']['duration'])
    except (ffmpeg.Error, KeyError):
        return 0.0

def analyze_scenes(manifest_file_path: str, output_directory: str):
    start_time = time.time()
    storage = StorageManager()

    # 1. Read the source manifest from GCS
    logging.info(f"Reading source manifest: {manifest_file_path}")
    manifest_data = storage.read(manifest_file_path)
    manifest = json.loads(manifest_data)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SceneAnalysisError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    
    model_name = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
    model = genai.GenerativeModel(model_name)

    video_files = [f['output_path'] for f in manifest.get('output_files', [])]
    if not video_files:
        raise SceneAnalysisError("No output files found in the manifest to analyze.")

    analysis_report_paths = []
    cumulative_time = 0.0

    for video_chunk_gcs_path in video_files:
        local_video_path = None
        try:
            # 2. Download each video chunk to a local temp file
            local_video_path = storage.get_local_path(video_chunk_gcs_path)
            
            logging.info(f"Uploading video chunk: {local_video_path} for GCS path {video_chunk_gcs_path}")
            video_file = genai.upload_file(path=local_video_path)
            
            while video_file.state.name == "PROCESSING":
                time.sleep(5)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name != "ACTIVE":
                raise SceneAnalysisError(f"File {video_file.name} failed to process.")

            # 3. Analyze content
            response = model.generate_content([GEMINI_PROMPT, video_file])
            response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            scene_data = json.loads(response_text)

            duration = _get_file_duration(local_video_path)
            scene_data['start_timestamp_seconds'] += cumulative_time
            scene_data['end_timestamp_seconds'] += cumulative_time
            
            # 4. Save individual chunk analysis JSON to GCS
            chunk_base_name = os.path.splitext(os.path.basename(video_chunk_gcs_path))[0]
            chunk_report_gcs_path = os.path.join(output_directory, f"{chunk_base_name}_analysis.json")
            storage.write_json(chunk_report_gcs_path, scene_data)

            analysis_report_paths.append(chunk_report_gcs_path)
            logging.info(f"Successfully analyzed and saved report to '{chunk_report_gcs_path}'.")
            
            cumulative_time += duration

        except Exception as e:
            logging.error(f"Failed to analyze scene for '{video_chunk_gcs_path}': {e}")
        finally:
            # 5. Clean up Gemini file and local temp file
            if 'video_file' in locals() and video_file:
                genai.delete_file(video_file.name)
            storage.cleanup_temp_files() # Cleans up the downloaded video

    return analysis_report_paths, time.time() - start_time