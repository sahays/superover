# LLD for Audio Extractor Module

## 1. Introduction

The Audio Extractor module is the second component in the Media Processing layer of Project Super Over. Its single job is to extract all audio streams from a video file. It produces separate files for each individual audio track and one file containing a mix-down of all tracks combined. This module will be implemented in Python and will provide both a command-line interface (CLI) and an API, both of which will output a structured JSON response.

## 2. Design Principles

- **Comprehensive Extraction:** The module must handle videos with single or multiple audio tracks.
- **Single Responsibility:** The module focuses exclusively on extracting and combining audio from video.
- **Efficiency:** The module will leverage a powerful, industry-standard backend (FFmpeg) for efficient processing.
- **Structured Output:** All outputs (CLI and API) will be in a consistent, machine-readable JSON format.

## 3. Module Architecture

The module will be contained within an `audio_extractor` directory.

```
audio_extractor/
├── __init__.py
├── main.py         # CLI entry point
├── api.py          # API entry point (e.g., using FastAPI)
├── extractor.py    # Core extraction logic
└── models.py       # Data models for input and output
```

## 4. Detailed Component Breakdown

### 4.1. `models.py` - Data Models

This file will define the data structures for API requests and the standardized JSON output.

**Pydantic Models:**

```python
from pydantic import BaseModel
from typing import Optional, List

class AudioExtractionRequest(BaseModel):
    video_file_path: str
    output_directory: Optional[str] = None # Directory to save files in

class ExtractedTrack(BaseModel):
    track_index: int
    output_path: str
    # Future metadata like language could be added here

class AudioExtractionResult(BaseModel):
    input_video_path: str
    combined_audio_path: str
    individual_tracks: List[ExtractedTrack]
    status: str
    message: str
```

### 4.2. `extractor.py` - Core Logic

This file will contain the core functionality for extracting and combining the audio streams.

**Dependencies:**
- `ffmpeg-python`

**Logic:**
1.  Use `ffmpeg.probe` to inspect the video file and identify all audio streams.
2.  If no audio streams are found, return an error.
3.  **For each identified audio stream:**
    -   Generate a unique output filename (e.g., `original-name_track-0.flac`).
    -   Use `ffmpeg` to extract the specific stream (`-map 0:a:0`, `-map 0:a:1`, etc.) to its file.
4.  **To combine streams:**
    -   Generate a unique output filename (e.g., `original-name_combined.flac`).
    -   Use `ffmpeg` with its `amerge` or `amix` filter from the `-filter_complex` option to mix down all audio streams into the combined file.
5.  Populate and return the `AudioExtractionResult` model.

**Functions:**

```python
def extract_audio(video_file_path: str, output_directory: str = None) -> dict:
    """
    Extracts all audio streams from a video file, creating both individual
    and combined audio files.

    Args:
        video_file_path: The absolute path to the input video file.
        output_directory: Optional. The directory to save the extracted files.
                          If not provided, files are saved in the same
                          directory as the video.

    Returns:
        A dictionary conforming to the AudioExtractionResult schema.
    """
    pass
```

### 4.3. `main.py` - CLI

**CLI Command:**

```bash
audio-extractor /path/to/video.mp4 --output-dir /path/to/save/
```

**Functionality:**
- Prints the `AudioExtractionResult` JSON to standard output.

### 4.4. `api.py` - API

**API Endpoint:**

- **Endpoint:** `POST /extract`
- **Request Body (`AudioExtractionRequest`):**
  ```json
  {
    "video_file_path": "/path/to/video.mp4",
    "output_directory": "/path/to/save/" // Optional
  }
  ```
- **Success Response (200 OK - `AudioExtractionResult`):**
  ```json
  {
    "input_video_path": "/path/to/video.mp4",
    "combined_audio_path": "/path/to/save/video_combined.flac",
    "individual_tracks": [
      {
        "track_index": 0,
        "output_path": "/path/to/save/video_track-0.flac"
      },
      {
        "track_index": 1,
        "output_path": "/path/to/save/video_track-1.flac"
      }
    ],
    "status": "success",
    "message": "Extracted 2 individual audio tracks and 1 combined track."
  }
  ```

## 5. Error Handling

- **FFmpeg Dependency:** The application will check for `ffmpeg` at startup.
- **File Not Found:** The application will check for the input file's existence.
- **No Audio Tracks:** The logic will handle cases where the video has no audio streams.
- **FFmpeg Errors:** All FFmpeg commands will be wrapped in error handling to catch processing failures.

## 6. Future Enhancements

- **Format Conversion:** Allow specifying the output audio codec (e.g., MP3, WAV).
- **Track Selection:** Allow the user to select a subset of tracks to extract or combine.
- **Metadata:** Extract and include audio track metadata (e.g., language, title) in the JSON output.