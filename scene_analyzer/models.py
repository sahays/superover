from pydantic import BaseModel, Field
from typing import List, Optional

class SceneAnalysisRequest(BaseModel):
    manifest_file_path: str

class CharacterDialogue(BaseModel):
    character_name: str = Field(description="The name of the character speaking.")
    dialogue: str = Field(description="The line of dialogue spoken by the character.")

class SceneAnalysis(BaseModel):
    start_timestamp_seconds: float = Field(description="Start time of the scene in seconds from the beginning of the original video.")
    end_timestamp_seconds: float = Field(description="End time of the scene in seconds from the beginning of the original video.")
    summary: str = Field(description="A concise, one-paragraph summary of the scene's plot and purpose.")
    setting: str = Field(description="A detailed description of the environment, e.g., 'A dimly lit, modern office at night, with rain visible on the windows.'")
    emotional_tone: str = Field(description="A single, descriptive term for the dominant emotion of the scene, e.g., 'Tense', 'Comedic', 'Somber'.")
    key_events: List[str] = Field(description="A list of the most important actions or plot developments that occur in this scene.")
    characters_present: List[str] = Field(description="A list of all characters who are visibly present in the scene.")
    dialogue_transcript: List[CharacterDialogue] = Field(description="A structured, chronological transcript of the dialogue.")
    visible_objects: List[str] = Field(description="A list of significant objects, vehicles, or symbols visible in the scene, e.g., ['Laptop', 'Red sports car', 'Golden key'].")
    camera_movement: str = Field(description="A description of the camera work, e.g., 'Static shot', 'Slow pan from left to right', 'Handheld shaky cam'.")
    sound_design: List[str] = Field(description="A list of notable non-dialogue sounds, e.g., ['Distant siren', 'Ticking clock', 'Sudden gunshot'].")

class SceneAnalysisResult(BaseModel):
    source_manifest_path: str
    analyzed_scenes: List[SceneAnalysis]
    status: str
    message: str
    time_taken_seconds: float
