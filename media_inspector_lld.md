# LLD for Media Inspector Module

## 1. Introduction

The Media Inspector module is a foundational component in the Media Processing layer of Project Super Over. Its sole responsibility is to read the technical metadata of a given media file (video or audio) and output it in a structured JSON format. This module will be implemented in Python and will provide both a command-line interface (CLI) and an API.

## 2. Design Principles

- **Single Responsibility:** The module does one thing and does it well: inspect media files.
- **Extensibility:** The module should be designed to easily add new metadata extraction capabilities in the future.
- **Ease of Use:** The CLI and API should be simple and intuitive.

## 3. Module Architecture

The module will be contained within a `media_inspector` directory.

```
media_inspector/
├── __init__.py
├── main.py         # CLI entry point
├── api.py          # API entry point (e.g., using FastAPI)
├── inspector.py    # Core inspection logic
└── models.py       # Data models (e.g., for metadata)
```

## 4. Detailed Component Breakdown

### 4.1. `inspector.py` - Core Logic

This file will contain the core functionality for extracting metadata.

**Dependencies:**
- `pymediainfo`: A Python wrapper for the MediaInfo library. This will be the primary tool for metadata extraction.

**Functions:**

```python
def inspect_media(file_path: str) -> dict:
    """
    Inspects a media file and returns its metadata.

    Args:
        file_path: The absolute path to the media file.

    Returns:
        A dictionary containing the media metadata.

    Raises:
        FileNotFoundError: If the file_path does not exist.
        MediaInspectionError: If the file is not a valid media file or cannot be inspected.
    """
    pass
```

### 4.2. `models.py` - Data Models

This file will define the structure of the JSON output. Using Pydantic for data validation is recommended.

**Pydantic Model:**

```python
from pydantic import BaseModel
from typing import List, Optional

class Track(BaseModel):
    track_type: str
    format: str
    codec: str
    bit_rate: Optional[str] = None
    # Video specific
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    # Audio specific
    sampling_rate: Optional[int] = None
    channels: Optional[int] = None

class MediaMetadata(BaseModel):
    file_name: str
    file_size: int # in bytes
    duration: float # in seconds
    tracks: List[Track]
```

### 4.3. `main.py` - CLI

This file will provide the command-line interface for the module.

**Dependencies:**
- `typer` or `click`: For creating the CLI.

**CLI Command:**

```bash
python -m media_inspector inspect /path/to/media.mp4
```

**Functionality:**
- Takes a file path as an argument.
- Calls `inspector.inspect_media()`.
- Prints the resulting JSON to standard output.
- Handles errors gracefully, printing user-friendly messages.

### 4.4. `api.py` - API

This file will expose the module's functionality as a REST API.

**Dependencies:**
- `fastapi`: For creating the API.
- `uvicorn`: For running the API server.

**API Endpoint:**

- **Endpoint:** `POST /inspect`
- **Request Body:**
  ```json
  {
    "file_path": "/path/to/media.mp4"
  }
  ```
- **Success Response (200 OK):**
  - The `MediaMetadata` JSON object.
- **Error Responses:**
  - `404 Not Found`: If the file does not exist.
  - `422 Unprocessable Entity`: If the request body is invalid.
  - `500 Internal Server Error`: For other processing errors.

## 5. Error Handling

- **File Not Found:** The application will check for the file's existence at the beginning of the process.
- **Invalid Media File:** The `pymediainfo` library will handle cases where the file is not a valid media file. The `inspector.py` module will catch these errors and raise a custom `MediaInspectionError`.
- **Permissions:** The application will handle `PermissionError` if the file cannot be read.

## 6. Future Enhancements

- **Cloud Storage Support:** Extend the module to inspect files directly from cloud storage URLs (e.g., S3, GCS).
- **Additional Metadata:** Add support for more detailed metadata, such as subtitles, chapters, and EXIF data.
