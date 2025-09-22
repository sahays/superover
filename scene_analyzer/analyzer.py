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

    if not os.path.exists(manifest_file_path):
        raise FileNotFoundError(f"Manifest file not found: {manifest_file_path}")

    with open(manifest_file_path, 'r') as f:
        manifest = json.load(f)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SceneAnalysisError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    
    model_name = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
    logging.info(f"Using Gemini model: {model_name}")
    model = genai.GenerativeModel(model_name)

    video_files = [f['output_path'] for f in manifest.get('output_files', [])]
    if not video_files:
        raise SceneAnalysisError("No output files found in the manifest to analyze.")

    analysis_report_paths = []
    cumulative_time = 0.0

    # Scene Deconstruction
    for i, video_chunk_path in enumerate(video_files):
        if not os.path.exists(video_chunk_path):
            logging.warning(f"Video file '{video_chunk_path}' from manifest not found. Skipping.")
            continue

        logging.info(f"Uploading video chunk: {video_chunk_path}")
        video_file = genai.upload_file(path=video_chunk_path)
        
        while video_file.state.name == "PROCESSING":
            logging.info(f"Waiting for file '{video_file.name}' to be processed...")
            time.sleep(5)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name != "ACTIVE":
            raise SceneAnalysisError(f"File {video_file.name} failed to process. Final state: {video_file.state.name}")

        logging.info(f"File '{video_file.name}' is now ACTIVE. Sending to model for analysis.")
        
        try:
            response = model.generate_content([GEMINI_PROMPT, video_file])
            response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            scene_data = json.loads(response_text)

            duration = _get_file_duration(video_chunk_path)
            scene_data['start_timestamp_seconds'] = cumulative_time
            scene_data['end_timestamp_seconds'] = cumulative_time + duration
            cumulative_time += duration

            # Save individual chunk analysis
            chunk_base_name = os.path.splitext(os.path.basename(video_chunk_path))[0]
            chunk_report_path = os.path.join(output_directory, f"{chunk_base_name}_analysis.json")
            
            with open(chunk_report_path, 'w', encoding='utf-8') as f:
                json.dump(scene_data, f, indent=4, ensure_ascii=False)

            analysis_report_paths.append(chunk_report_path)
            logging.info(f"Successfully analyzed and saved report for '{video_chunk_path}' to '{chunk_report_path}'.")

        except Exception as e:
            logging.error(f"Failed to analyze scene for '{video_chunk_path}': {e}")
        finally:
            genai.delete_file(video_file.name)

    return analysis_report_paths, time.time() - start_time
