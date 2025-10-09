# Firestore Database Schema

## Collection Naming Convention

Pattern: `{workflow}_{entity}`

- **Media workflow**: `media_jobs`
- **Scene workflow**: `scene_jobs`, `scene_tasks`, `scene_results`, `scene_manifests`, `scene_prompts`
- **Shared**: `videos` (used by both workflows)

## Collections

### Core Collections

#### `videos`
Source video records (shared by both workflows)
```
{video_id}/
  - video_id: string
  - filename: string
  - gcs_path: string (GCS path to original uploaded video)
  - content_type: string
  - size_bytes: number
  - status: VideoStatus enum
  - created_at: timestamp
  - updated_at: timestamp
  - metadata: object
  - error_message: string (optional)
```

#### `scene_manifests`
Scene processing metadata (chunks, audio, compressed video from scene workflow)
```
{video_id}/
  - video_id: string
  - created_at: timestamp
  - original: object (metadata)
  - compressed: object (gcs_path, size, etc.)
  - chunks: object (count, duration_per_chunk, items[])
  - audio: object (gcs_path, format, etc.)
```

### Job Collections

#### `media_jobs`
Media processing jobs (compression, audio extraction)
```
{job_id}/
  - job_id: string
  - video_id: string
  - status: MediaJobStatus enum (pending, processing, completed, failed)
  - config: object
    - compress: boolean
    - compress_resolution: string (480p, 720p, etc.)
    - extract_audio: boolean
    - audio_format: string (mp3, aac, etc.)
    - audio_bitrate: string
    - crf: number
    - preset: string
  - results: object (optional)
    - metadata: object
    - compressed_video_path: string
    - audio_path: string
    - original_size_bytes: number
    - compressed_size_bytes: number
    - compression_ratio: number
  - progress: object (optional)
    - step: string
    - percent: number
  - created_at: timestamp
  - updated_at: timestamp
  - error_message: string (optional)
```

#### `scene_jobs`
Scene analysis jobs (chunking + Gemini analysis)
```
{job_id}/
  - job_id: string
  - video_id: string
  - status: SceneJobStatus enum (pending, processing, completed, failed)
  - config: object
    - chunk_duration: number (seconds, 0 = no chunking)
    - prompt_version: number
    - scene_types: array (scene, objects, transcription, moderation)
  - task_ids: array (list of scene_task IDs)
  - results: object (optional)
    - total_chunks: number
    - analyzed_chunks: number
    - summary: object
  - created_at: timestamp
  - updated_at: timestamp
  - error_message: string (optional)
```

### Task & Result Collections

#### `scene_tasks`
Individual chunk analysis tasks
```
{task_id}/
  - task_id: string
  - video_id: string
  - scene_job_id: string (link to parent scene_jobs)
  - task_type: string (scene_scene, scene_objects, etc.)
  - status: TaskStatus enum (pending, processing, completed, failed)
  - input_data: object
    - chunk: object (chunk metadata)
    - scene_type: string
  - result_data: object (optional)
  - created_at: timestamp
  - updated_at: timestamp
  - error_message: string (optional)
```

#### `scene_results`
Gemini analysis results
```
{auto_generated_id}/
  - video_id: string
  - scene_job_id: string (link to parent scene_jobs)
  - result_type: string (scene_analysis, transcription, etc.)
  - result_data: object (Gemini response)
  - gcs_path: string (optional, for large results)
  - created_at: timestamp
```

#### `scene_prompts`
Analysis prompts (task-level, not chunk-level)
```
{prompt_type}/
  - prompt_type: string (scene_analysis, object_detection, etc.)
  - version: number
  - prompt_text: string
  - status: string (active, archived)
  - created_at: timestamp
  - updated_at: timestamp
  - description: string
```

## Workflow Separation

### Media Workflow (`/media`)
1. Upload video → Creates `videos` record
2. Start media job → Creates `media_jobs` record
3. Worker processes → Updates `media_jobs` with results (compressed video, audio)

### Scene Workflow (`/scene-analysis`)
1. Pick processed video (from media workflow)
2. Configure chunking → Creates `scene_jobs` record
3. Worker chunks video → Creates `scene_tasks` for each chunk
4. Worker analyzes chunks → Creates `scene_results` for each task
5. Updates `scene_manifests` with chunk metadata

## Deletion Rules

### Delete Scene (`DELETE /api/scenes/{video_id}`)
Deletes:
- `scene_manifests/{video_id}`
- All `scene_jobs` for video
- All `scene_tasks` for video
- All `scene_results` for video
- All `scene_prompts` for video
- GCS files: compressed video, chunks, audio (from scene workflow)

Preserves:
- `videos/{video_id}` record (reset status to "uploaded")
- Original video file in GCS
- All `media_jobs` for video

### Delete Media Job (`DELETE /api/media/jobs/{job_id}`)
Deletes:
- `media_jobs/{job_id}`
- GCS files: compressed video, audio (from this job only)

Preserves:
- `videos/{video_id}` record
- Original video file in GCS
- Other media jobs for same video

## Migration Notes

**2025-01-XX**: Renamed collections for clarity
- `manifests` → `scene_manifests`
- `analysis_tasks` → `scene_tasks`
- `results` → `scene_results`
- `prompts` → `scene_prompts`
- Added `scene_jobs` collection
- Kept `media_jobs` as is
