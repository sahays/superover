import { z } from 'zod'

// Enums
export enum MediaJobStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum SceneJobStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

// Zod Schemas
export const videoSchema = z.object({
  video_id: z.string(),
  filename: z.string(),
  gcs_path: z.string(),
  status: z.string(), // Allow any string for status
  content_type: z.string().optional(),
  size_bytes: z.number().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  metadata: z.record(z.any()).optional(),
  error_message: z.string().optional(),
})

export const sceneJobSchema = z.object({
  job_id: z.string(),
  video_id: z.string(),
  status: z.nativeEnum(SceneJobStatus),
  config: z.record(z.any()),
  prompt_text: z.string(),
  prompt_type: z.string().optional(),
  prompt_name: z.string().optional(),
  results: z.record(z.any()).optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  error_message: z.string().optional(),
})

export const manifestSchema = z.object({
  video_id: z.string(),
  version: z.string(),
  original: z.record(z.any()),
  compressed: z.record(z.any()).optional(),
  chunks: z.object({
    count: z.number(),
    duration_per_chunk: z.number(),
    items: z.array(z.any()),
  }).optional(),
  audio: z.record(z.any()).optional(),
  processing: z.record(z.any()).optional(),
})

export const resultSchema = z.object({
  result_id: z.string(),
  video_id: z.string(),
  result_type: z.string(),
  result_data: z.record(z.any()),
  gcs_path: z.string().optional(),
  created_at: z.string().optional(),
})

// TypeScript Types
export type Video = z.infer<typeof videoSchema>
export type SceneJob = z.infer<typeof sceneJobSchema>
export type Manifest = z.infer<typeof manifestSchema>
export type Result = z.infer<typeof resultSchema>

// Upload form schema
export const uploadFormSchema = z.object({
  file: z.instanceof(File).refine((file) => file.size <= 500 * 1024 * 1024, {
    message: 'File size must be less than 500MB',
  }).refine((file) => file.type.startsWith('video/'), {
    message: 'File must be a video',
  }),
})

export type UploadFormData = z.infer<typeof uploadFormSchema>

// Media Processing Types
export const mediaProcessingConfigSchema = z.object({
  compress: z.boolean().default(true),
  compress_resolution: z.string().default('480p'),
  extract_audio: z.boolean().default(true),
  audio_format: z.string().default('mp3'),
  audio_bitrate: z.string().default('128k'),
  crf: z.number().default(23),
  preset: z.string().default('medium'),
})

export const mediaJobResultsSchema = z.object({
  metadata: z.record(z.any()),
  compressed_video_path: z.string().optional(),
  audio_path: z.string().optional(),
  original_size_bytes: z.number().default(0),
  compressed_size_bytes: z.number().default(0),
  compression_ratio: z.number().default(0),
  audio_size_bytes: z.number().default(0),
})

export const mediaJobSchema = z.object({
  job_id: z.string(),
  video_id: z.string(),
  status: z.nativeEnum(MediaJobStatus),
  config: mediaProcessingConfigSchema,
  results: mediaJobResultsSchema.optional(),
  progress: z.record(z.any()).optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  error_message: z.string().optional(),
})

export const mediaPresetSchema = z.object({
  resolutions: z.array(z.string()),
  audio_formats: z.array(z.string()),
  audio_bitrates: z.array(z.string()),
  presets: z.array(z.string()),
  crf_range: z.object({
    min: z.number(),
    max: z.number(),
    default: z.number(),
  }),
})

export type MediaProcessingConfig = z.infer<typeof mediaProcessingConfigSchema>
export type MediaJobResults = z.infer<typeof mediaJobResultsSchema>
export type MediaJob = z.infer<typeof mediaJobSchema>
export type MediaPreset = z.infer<typeof mediaPresetSchema>

// Prompt Management Types
export const promptSchema = z.object({
  prompt_id: z.string(),
  name: z.string(),
  type: z.string(),
  prompt_text: z.string(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  jobs_count: z.number().optional(),
})

export type Prompt = z.infer<typeof promptSchema>
