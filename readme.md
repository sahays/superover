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

| Module Name (.py)         | Purpose (Its Single Job)                                                          | Primary Input(s)                                                         | Primary Output(s)                                                                              |
| :------------------------ | :-------------------------------------------------------------------------------- | :----------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| **media_inspector**       | 🔍 Reads the technical metadata of a media file.                                  | A file path to a video or audio file.                                    | A JSON object with properties (e.g., resolution, fps, duration).                               |
| **audio_extractor**       | 🎵 Extracts the audio stream from a video file.                                   | A file path to a video file.                                             | A standalone audio file (e.g., /path/to/audio.flac).                                           |
| **video_splitter**        | 🪓 Slices a video file into multiple smaller clips.                               | A video file path and a list of (start, end) timestamps.                 | A list of file paths to the new video clips.                                                   |
| **video_chunker**         | 🧱 Breaks any video clip into fixed-duration chunks.                              | A video file path and a duration in seconds (e.g., 5).                   | A list of file paths to the chunked video files.                                               |
| **video_compressor**      | Compresses a video file by resolution                                             | A video file                                                             | A compressed video file.                                                                       |
| **scene_analyzer**        | ✨ Takes a media chunk, sends it to Gemini, and retrieves the rich JSON metadata. | A video chunk file path and its corresponding audio chunk.               | A single JSON object with metadata for that chunk (characters, emotions, actions, transcript). |
| **engagement_correlator** | 📈 Aligns engagement events to specific time-coded scenes.                        | A list of Scene objects with timestamps and a list of engagement events. | The same list of Scene objects, now enriched with aggregated engagement data.                  |
| **character_tracker**     | 👤 Filters all scene data to create a timeline for a single character.            | A list of all Scene JSON objects and a character name.                   | A JSON object detailing that character's arc (screen time, emotional journey).                 |
| **relationship_mapper**   | 🔗 Analyzes all interactions between two specific characters.                     | A list of all Scene JSON objects and two character names.                | A JSON report on the relationship's evolution (e.g., sentiment change over time).              |
| **dialogue_generator**    | 💬 Generates alternative lines of dialogue for a scene.                           | A Scene JSON object and a creative prompt (e.g., "make this funnier").   | A JSON object with a list of {'dialogue_options': \[...\]}.                                    |
| **plot_suggester**        | 💡 Brainstorms potential plot developments based on a scene's context.            | A Scene JSON object.                                                     | A JSON object with a list of {'plot_twists': \[...\]}.                                         |
