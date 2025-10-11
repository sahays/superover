import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Scene endpoints
export const videoApi = {
  getSignedUrl: async (filename: string, contentType: string) => {
    const response = await apiClient.post('/api/scenes/signed-url', {
      filename,
      content_type: contentType,
    })
    return response.data
  },

  createVideo: async (data: {
    filename: string
    gcs_path: string
    content_type: string
    size_bytes: number
  }) => {
    const response = await apiClient.post('/api/scenes', data)
    return response.data
  },

  getVideo: async (videoId: string) => {
    const response = await apiClient.get(`/api/scenes/${videoId}`)
    return response.data
  },

  listVideos: async (limit = 50) => {
    const response = await apiClient.get('/api/scenes', {
      params: { limit },
    })
    return response.data
  },

  processVideo: async (videoId: string, options: {
    prompt_id: string
    compressed_video_path?: string
    chunk_duration?: number
    chunk?: boolean
    compress?: boolean
    extract_audio?: boolean
  }) => {
    const response = await apiClient.post(`/api/scenes/${videoId}/process`, {
      compress: false,
      chunk: true,
      extract_audio: false,
      chunk_duration: 30,
      ...options,
    })
    return response.data
  },

  analyzeScenes: async (
    videoId: string,
    sceneTypes = ['scene', 'objects', 'transcription', 'moderation']
  ) => {
    const response = await apiClient.post(`/api/scenes/${videoId}/scene-analysis`, {
      scene_types: sceneTypes,
    })
    return response.data
  },

  getManifest: async (videoId: string) => {
    const response = await apiClient.get(`/api/scenes/${videoId}/manifest`)
    return response.data
  },

  getResults: async (videoId: string, resultType?: string) => {
    const response = await apiClient.get(`/api/scenes/${videoId}/results`, {
      params: resultType ? { result_type: resultType } : {},
    })
    return response.data
  },

  deleteVideo: async (videoId: string) => {
    const response = await apiClient.delete(`/api/scenes/${videoId}`)
    return response.data
  },
}

// Scene job endpoints
export const sceneJobApi = {
  listJobs: async (limit = 50, status?: string) => {
    const response = await apiClient.get('/api/scenes/jobs', {
      params: { limit, status_filter: status },
    })
    return response.data
  },

  getJob: async (jobId: string) => {
    const response = await apiClient.get(`/api/scenes/jobs/${jobId}`)
    return response.data
  },

  getResults: async (jobId: string, resultType?: string) => {
    const response = await apiClient.get(`/api/scenes/jobs/${jobId}/results`, {
      params: resultType ? { result_type: resultType } : {},
    })
    return response.data
  },

  deleteJob: async (jobId: string) => {
    const response = await apiClient.delete(`/api/scenes/jobs/${jobId}`)
    return response.data
  },
}

// Task endpoints
export const taskApi = {
  getTask: async (taskId: string) => {
    const response = await apiClient.get(`/api/tasks/${taskId}`)
    return response.data
  },

  listTasksForVideo: async (videoId: string) => {
    const response = await apiClient.get(`/api/tasks/video/${videoId}`)
    return response.data
  },
}

// Media processing endpoints
export const mediaApi = {
  createJob: async (data: {
    video_id: string
    config?: {
      compress?: boolean
      compress_resolution?: string
      extract_audio?: boolean
      audio_format?: string
      audio_bitrate?: string
      crf?: number
      preset?: string
    }
  }) => {
    const response = await apiClient.post('/api/media/jobs', data)
    return response.data
  },

  getJob: async (jobId: string) => {
    const response = await apiClient.get(`/api/media/jobs/${jobId}`)
    return response.data
  },

  listJobsForVideo: async (videoId: string, status?: string) => {
    const response = await apiClient.get(`/api/media/jobs/video/${videoId}`, {
      params: status ? { status_filter: status } : {},
    })
    return response.data
  },

  deleteJob: async (jobId: string) => {
    const response = await apiClient.delete(`/api/media/jobs/${jobId}`)
    return response.data
  },

  getPresets: async () => {
    const response = await apiClient.get('/api/media/presets')
    return response.data
  },

  getAllVideosWithJobs: async () => {
    const response = await apiClient.get('/api/media/videos-with-jobs')
    return response.data
  },

  listVideos: async (limit = 50) => {
    const response = await apiClient.get('/api/media/videos', {
      params: { limit },
    })
    return response.data
  },
}

// Prompt management endpoints
export const promptApi = {
  listPrompts: async () => {
    const response = await apiClient.get('/api/prompts')
    return response.data
  },

  getPrompt: async (promptId: string) => {
    const response = await apiClient.get(`/api/prompts/${promptId}`)
    return response.data
  },

  createPrompt: async (data: { name: string; type: string; prompt_text: string }) => {
    const response = await apiClient.post('/api/prompts', data)
    return response.data
  },

  updatePrompt: async (promptId: string, data: { name?: string; type?: string; prompt_text?: string }) => {
    const response = await apiClient.put(`/api/prompts/${promptId}`, data)
    return response.data
  },

  deletePrompt: async (promptId: string) => {
    const response = await apiClient.delete(`/api/prompts/${promptId}`)
    return response.data
  },
}

// Upload file to GCS using signed URL
export const uploadToGCS = async (signedUrl: string, file: File) => {
  await axios.put(signedUrl, file, {
    headers: {
      'Content-Type': file.type,
    },
  })
}
