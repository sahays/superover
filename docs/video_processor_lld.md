# LLD for Video Processor Module

## 1. Introduction

The Video Processor module is a component in the Media Processing layer that consolidates the functionality of splitting, chunking, and compressing video files. It is designed to act as a configurable pipeline, where a source video can undergo a series of sequential operations based on user-provided switches. For example, a user can choose to split a video into scenes and then compress each of those scenes.

This module replaces the need for separate `video_splitter`, `video_chunker`, and `video_compressor` modules.

## 2. Design Principles

- **Consolidation:** Combine related video processing tasks into a single, intuitive interface.
- **Pipeline Architecture:** The operations are applied sequentially: `Split/Chunk` -> `Compress`.
- **Clarity and Control:** The CLI and API will use clear switches to control the processing steps. It will enforce logical constraints, such as the mutual exclusivity of splitting and chunking.
- **Structured Output:** The module will produce a detailed JSON output summarizing the operations performed and listing all the generated files.

## 3. Module Architecture

The module will be contained within a `video_processor` directory.

```
video_processor/
├── __init__.py
├── main.py         # CLI entry point
├── api.py          # API entry point (e.g., using FastAPI)
├── processor.py    # Core processing pipeline logic
└── models.py       # Data models for input and output
```

## 4. Detailed Component Breakdown

### 4.1. `models.py` - Data Models

This file will define the data structures for the API and the standardized JSON output.

**Pydantic Models:**

```python
from pydantic import BaseModel
from typing import Optional, List

class VideoProcessingRequest(BaseModel):
    video_file_path: str
    output_directory: Optional[str] = None
    split_timestamps: Optional[str] = None # e.g., "00:10-00:20,01:30-01:45"
    chunk_duration: Optional[int] = None   # e.g., 5 (in seconds)
    compress_resolution: Optional[str] = None # e.g., "1280x720" or "720p", "4K", etc.
    compress_first: Optional[bool] = False # If true, compress before splitting/chunking

class ProcessedFile(BaseModel):
    output_path: str


class VideoProcessingResult(BaseModel):
    input_video_path: str
    operations_performed: List[str]
    output_files: List[ProcessedFile]
    status: str
    message: str
    time_taken_seconds: float
```

### 4.2. `processor.py` - Core Logic

This file will contain the core pipeline for processing the video.

**Dependencies:**
- `ffmpeg-python`

**Pipeline Logic:**
The main function, `process_video`, will orchestrate the operations.

1.  **Input Validation:**
    -   Check if `video_file_path` exists.
    -   Check that `split_timestamps` and `chunk_duration` are not provided at the same time, as they are mutually exclusive. Raise an error if they are.
2.  **Initialization:**
    -   Start with a list of files to process, initially containing just the `video_file_path`.
    -   Keep a list of operations performed (e.g., `["split", "compress"]`).
3.  **Step 1: Splitting or Chunking (if requested)**
    -   If `split_timestamps` is provided, call an internal `_split_video` function. This function will use FFmpeg's segmenting capabilities to create multiple clips. The list of files to process is replaced by the list of newly created clip paths.
    -   *Else if* `chunk_duration` is provided, call an internal `_chunk_video` function. This will use FFmpeg to break the video into fixed-duration chunks. The list of files is replaced by the new chunk paths.
4.  **Step 2: Compression (if requested)**
    -   If `compress_resolution` is provided, call an internal `_compress_videos` function. This function iterates through the current list of files (which could be the original video, or the clips from Step 1) and creates a compressed version of each one using FFmpeg's scaling (`scale`) filter. The list of files is replaced by the paths of the compressed files.
5.  **Final Output:**
    -   Collate all the final file paths into the `VideoProcessingResult` model.
    -   Return the result as a dictionary.

### 4.3. `main.py` - CLI

**Dependencies:**
- `click`

**CLI Command:**

```bash
# Example 1: Split a video into two clips
video-processor /path/to/video.mp4 --split-timestamps "00:10-00:20,01:30-01:45"

# Example 2: Chunk a video into 10-second clips and then compress them to 720p
video-processor /path/to/video.mp4 --chunk-duration 10 --compress-resolution "1280x720"

# Example 3: Just compress a video
video-processor /path/to/video.mp4 --compress-resolution "640x360"
```

**Functionality:**
- The CLI will use `click` options to accept the processing parameters.
- It will call the `processor.process_video` function and print the resulting JSON to standard output.
- Help text will clarify that `--split-timestamps` and `--chunk-duration` cannot be used together.

### 4.4. `api.py` - API

**Dependencies:**
- `fastapi`

**API Endpoint:**

- **Endpoint:** `POST /process`
- **Request Body (`VideoProcessingRequest`):**
  ```json
  {
    "video_file_path": "/path/to/video.mp4",
    "chunk_duration": 10,
    "compress_resolution": "1280x720"
  }
  ```
- **Success Response (200 OK - `VideoProcessingResult`):**
  ```json
  {
    "input_video_path": "/path/to/video.mp4",
    "operations_performed": ["chunk", "compress"],
    "output_files": [
      {
        "output_path": "/path/to/output/video_chunk_0_compressed.mp4",
        "source_operation": "compress"
      },
      {
        "output_path": "/path/to/output/video_chunk_1_compressed.mp4",
        "source_operation": "compress"
      }
    ],
    "status": "success",
    "message": "Successfully processed video."
  }
  ```

## 5. Error Handling

- **FFmpeg Dependency:** Check for `ffmpeg` at startup.
- **Mutual Exclusion:** The core logic will raise an error if conflicting options are provided.
- **Invalid Arguments:** Handle invalid timestamp formats or resolution strings.
- **FFmpeg Errors:** All FFmpeg commands will be wrapped in error handling.

## 6. Future Enhancements

- **More Operations:** Add other processing steps like watermarking, adding text overlays, or changing codecs.
- **Complex Pipelines:** Allow for more complex, user-defined ordering of operations.
- **Metadata Passthrough:** Ensure important metadata is retained in the output files.
