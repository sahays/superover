# LLD for Scene Analyzer Module

## 1. Introduction

The Scene Analyzer module is the first component in the **Core AI Analysis** layer. It takes the JSON manifest from a media processing tool, sends each video chunk to the Gemini API, and retrieves a rich, scene-by-scene analysis of the content. It includes an optional second-pass analysis to normalize character names across all scenes.

## 2. Design Principles

- **Composability:** Consumes JSON manifests from upstream tools to create a seamless pipeline.
- **AI-Powered:** Leverages the Gemini Pro Vision model for deep content understanding and a text model for character recognition.
- **Structured Output:** Produces a detailed, validated JSON output for easy downstream consumption.
- **Transparent Pipeline:** When character recognition is enabled, the tool saves both the raw first-pass analysis and the final second-pass analysis for clarity and debugging.

## 3. Module Architecture

```
scene_analyzer/
├── __init__.py
├── main.py         # CLI entry point
├── api.py          # API entry point
├── analyzer.py     # Core analysis logic
└── models.py       # Pydantic models for validation
```

## 4. Detailed Component Breakdown

### 4.1. Output Schema

The module's primary output is a `SceneAnalysisResult` JSON object. The `analyzed_scenes` field contains a list of `SceneAnalysis` objects. A key sub-model is `CharacterDialogue`, which has the following structure:

| Field Name          | Type     | Description                                     |
| :------------------ | :------- | :---------------------------------------------- |
| `character_name`    | `string` | The name of the character speaking.             |
| `dialogue`          | `string` | The line of dialogue spoken by the character.   |
| `detected_language` | `string` | The detected language of the dialogue (e.g., "English", "Telugu"). |

*(For the full `SceneAnalysis` schema, see the `models.py` file.)*

### 4.2. Core Logic (`analyzer.py`)

The core logic uses a two-pass approach:

1.  **First Pass (Scene Deconstruction):** The tool iterates through each video chunk, sending it to the Gemini vision model to generate the initial `SceneAnalysisResult` JSON. The prompt instructs the model to identify the language of any spoken dialogue.

2.  **Second Pass (Character Recognition):** If the `--recognize-people` flag is active, the system sends the entire JSON from the first pass to a Gemini text model. A specialized prompt instructs the model to normalize character names.

The function returns both the first-pass and second-pass results.

### 4.3. Interfaces (CLI & API)

**CLI Command:**
The tool is invoked by passing the path to a manifest file. When `--recognize-people` is used, two output files are generated.

```bash
# This will create one file: my_report_analyzed.json
scene-analyzer ./video-output/my_report.json --output-dir ./analysis

# This will create two files: my_report_analyzed_raw.json and my_report_analyzed_final.json
scene-analyzer ./video-output/my_report.json --output-dir ./analysis --recognize-people
```

**API Endpoint:**
- **`POST /analyze`**
- **Request Body:**
  ```json
  {
    "manifest_file_path": "/path/to/report.json",
    "recognize_people": true
  }
  ```
- **Response:** The API will return the final, second-pass analysis if `recognize_people` is true, or the first-pass analysis otherwise.

## 5. Error Handling

The system will gracefully handle invalid manifests, missing media files, Gemini API errors, and malformed JSON responses from the model during both passes. The file writing logic will use UTF-8 encoding to correctly handle all languages.