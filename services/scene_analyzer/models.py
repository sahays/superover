from pydantic import BaseModel, Field
from typing import List, Optional

class SceneAnalysisRequest(BaseModel):
    manifest_file_path: str

class CharacterDialogue(BaseModel):
    character_name: str = Field(description="The name of the character speaking.")
    dialogue: str = Field(description="The line of dialogue spoken by the character.")
    detected_language: str = Field(description="The detected language of the dialogue, e.g., 'English', 'Telugu'.")
    start_timestamp_seconds: float = Field(description="The timestamp (in seconds) when the dialogue begins.")

class KeyEvent(BaseModel):
    event: str = Field(description="A key event or action.")
    start_timestamp_seconds: float = Field(description="The timestamp (in seconds) when the event occurs.")

class VisibleObject(BaseModel):
    object: str = Field(description="A significant visible object.")
    start_timestamp_seconds: float = Field(description="The timestamp (in seconds) when the object first appears or becomes significant.")

class SoundEffect(BaseModel):
    sound: str = Field(description="A notable non-dialogue sound.")
    start_timestamp_seconds: float = Field(description="The timestamp (in seconds) when the sound occurs.")

class ModerationFlag(BaseModel):
    flag: str = Field(description="A content moderation flag, e.g., 'Violence'.")
    start_timestamp_seconds: float = Field(description="The timestamp (in seconds) when the flagged content appears.")

class BrandRecognition(BaseModel):
    brand_name: str = Field(description="The recognized brand name.")
    object_type: str = Field(description="The type of object the brand is associated with.")
    description: str = Field(description="A brief description of where the brand appears.")
    start_timestamp_seconds: float = Field(description="The timestamp (in seconds) when the brand appears.")

class SceneAnalysis(BaseModel):
    start_timestamp_seconds: float = Field(description="Start time of the scene in seconds.")
    end_timestamp_seconds: float = Field(description="End time of the scene in seconds.")
    summary: str = Field(description="A concise summary of the scene.")
    setting: str = Field(description="A detailed description of the environment.")
    emotional_tone: str = Field(description="The dominant emotion of the scene.")
    key_events: List[KeyEvent] = Field(description="A list of key events with timestamps.")
    characters_present: List[str] = Field(description="A list of all characters present.")
    dialogue_transcript: List[CharacterDialogue] = Field(description="A structured transcript with timestamps.")
    visible_objects: List[VisibleObject] = Field(description="A list of significant objects with timestamps.")
    camera_movement: str = Field(description="A description of the camera work.")
    sound_design: List[SoundEffect] = Field(description="A list of notable sounds with timestamps.")
    moderation_flags: List[ModerationFlag] = Field(description="A list of moderation flags with timestamps.")
    brand_recognition: List[BrandRecognition] = Field(description="A list of recognized brands with timestamps.")

class SceneAnalysisResult(BaseModel):
    source_manifest_path: str
    analysis_reports: List[str]
    status: str
    message: str
    time_taken_seconds: float