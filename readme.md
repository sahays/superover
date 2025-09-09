# **Super Over Technical Summary**

## **1\. Project Summary**

**Project Super Over** is a Gemini-powered narrative analytics platform that combines audience engagement data and
creative decision-making for streaming platforms. The system deconstructs video content scene-by-scene—analyzing
characters, dialogue, and emotional tone—and correlates these narrative elements directly with viewer behavior like
drop-offs and plays. This provides writers, showrunners, and studio executives with unprecedented, data-driven insights
to optimize plotlines, enhance character arcs, and ultimately de-risk future productions by creating content that more
effectively retains its audience.

---

## **2\. System Architecture: The Component Library**

The system is designed as a collection of discrete, single-purpose modules, or "LEGO blocks." This design ensures
maximum flexibility, allowing any component to be used independently or composed into a larger workflow. The library is
organized into three layers: foundational **Media Processing**, **Core AI Analysis**, and high-level **Narrative
Synthesis**.

Each module will have its own folder e.g. media_inspector with a CLI and API frontend. A root cli can invoke each module
separately. Use python libs for CLI and API authoring.

---

## **3\. Module Breakdown**

The following table details each individual component within the library, outlining its specific purpose, inputs, and
outputs.

| Module Name (.py)         | Purpose (Its Single Job)                                                          | Primary Input(s)                                                             | Primary Output(s)                                                                              |
| :------------------------ | :-------------------------------------------------------------------------------- | :--------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| **media_inspector**       | 🔍 Reads the technical metadata of a media file.                                  | A file path to a video or audio file.                                        | A JSON object with properties (e.g., resolution, fps, duration).                               |
| **audio_extractor**       | 🎵 Extracts the audio stream from a video file.                                   | A file path to a video file.                                                 | A JSON object detailing the input path, output path, and status.                               |
| **video_processor**       | 📼 Splits, chunks, and/or compresses video files in a configurable pipeline.      | A file path to a video file and operation switches (e.g., --chunk-duration). | A JSON object detailing all the operations performed and the output file paths.                |
| **scene_analyzer**        | ✨ Takes a media chunk, sends it to Gemini, and retrieves the rich JSON metadata. | A video chunk file path and its corresponding audio chunk.                   | A single JSON object with metadata for that chunk (characters, emotions, actions, transcript). |
| **engagement_correlator** | 📈 Aligns engagement events to specific time-coded scenes.                        | A list of Scene objects with timestamps and a list of engagement events.     | The same list of Scene objects, now enriched with aggregated engagement data.                  |
| **character_tracker**     | 👤 Filters all scene data to create a timeline for a single character.            | A list of all Scene JSON objects and a character name.                       | A JSON object detailing that character's arc (screen time, emotional journey).                 |
| **relationship_mapper**   | 🔗 Analyzes all interactions between two specific characters.                     | A list of all Scene JSON objects and two character names.                    | A JSON report on the relationship's evolution (e.g., sentiment change over time).              |
| **dialogue_generator**    | 💬 Generates alternative lines of dialogue for a scene.                           | A Scene JSON object and a creative prompt (e.g., "make this funnier").       | A JSON object with a list of {'dialogue_options': \[...\]}.                                    |
| **plot_suggester**        | 💡 Brainstorms potential plot developments based on a scene's context.            | A Scene JSON object.                                                         | A JSON object with a list of {'plot_twists': \[...\]}.                                         |

---

## **4. Command-Line Tool Usage**

After installing the project with `pip install -e .`, the following command-line tools are available.

### **`media-inspector`**

Inspects a media file and prints its technical metadata as a JSON object.

```bash
media-inspector /path/to/your/video.mov
```

### **`audio-extractor`**

Extracts all audio tracks from a video file. It creates a separate file for each track and one combined file with all
tracks mixed together.

```bash
# Basic usage
audio-extractor /path/to/your/video.mp4

# Specify an output directory for the extracted files
audio-extractor /path/to/your/video.mp4 --output-dir ./audio_files
```

### **`video-processor`**

A multi-purpose tool to split, chunk, and/or compress video files. Operations can be chained together.

**Common Options:**

- `--output-dir <path>`: Specify a directory for all output files.
- `--compress-first`: If present, compression will be performed _before_ splitting or chunking.

**Examples:**

```bash
# Compress a video to 720p
video-processor /path/to/video.mp4 --compress-resolution 720p

# Chunk a video into 10-second segments
video-processor /path/to/video.mp4 --chunk-duration 10

# Split a video into specific scenes
video-processor /path/to/video.mp4 --split-timestamps "00:01:30-00:02:00,00:05:15-00:06:00"

# Chunk a video into 30-second clips, then compress each clip to 480p
video-processor /path/to/video.mp4 --chunk-duration 30 --compress-resolution 480p

# Compress a video to 1080p first, then split the compressed video into scenes
video-processor /path/to/video.mp4 --compress-resolution 1080p --split-timestamps "00:10:00-00:12:30" --compress-first
```

### **`scene-analyzer`**

Takes the JSON report from `video-processor` as input, analyzes each video chunk via the Gemini API, and outputs a new, highly-detailed JSON analysis file.

**Prerequisites:**
- A `GEMINI_API_KEY` must be set in the `.env` file at the project root.

**Example:**

```bash
# Create a directory for the analysis output
mkdir ./analysis_output

# Run the analyzer on a report from the video-processor
scene-analyzer ./video-output/my_video_report.json --output-dir ./analysis_output
```

---

## **5. Internal Documentation**

For more detailed technical designs, please see the Low-Level Design (LLD) documents for each module:

- [Media Inspector LLD](./docs/media_inspector_lld.md)
- [Audio Extractor LLD](./docs/audio_extractor_lld.md)
- [Video Processor LLD](./docs/video_processor_lld.md)
- [Scene Analyzer LLD](./docs/scene_analyzer_lld.md)
