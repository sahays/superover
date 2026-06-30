import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '@/store/useAuthStore'

export const apiClient = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Attach X-Invite-Code header to every request
apiClient.interceptors.request.use((config) => {
  const code = useAuthStore.getState().inviteCode
  if (code) {
    config.headers['X-Invite-Code'] = code
  }
  return config
})

// Global error handler: 401/403 auto-logout + 429 rate limit
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      useAuthStore.getState().logout()
    }
    if (error.response?.status === 429) {
      const data = error.response.data?.detail || error.response.data
      const retryMinutes = Math.ceil((data?.retry_after || 600) / 60)
      toast.error('Rate limit reached', {
        description: `Maximum requests exceeded. Try again in ${retryMinutes} minutes.`,
      })
    }
    return Promise.reject(error)
  }
)

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
    metadata?: Record<string, unknown>
    owner?: string
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
    context_items?: Array<{
      context_id: string
      type: string
      gcs_path: string
      filename: string
      description?: string
      size_bytes: number
    }>
  }) => {
    const payload = {
      compress: false,
      chunk: true,
      extract_audio: false,
      chunk_duration: 30,
      ...options,
    }
    console.log('=== processVideo API call ===')
    console.log('videoId:', videoId)
    console.log('payload:', JSON.stringify(payload, null, 2))
    console.log('chunk_duration in payload:', payload.chunk_duration, 'type:', typeof payload.chunk_duration)

    const response = await apiClient.post(`/api/scenes/${videoId}/process`, payload)
    return response.data
  },

  getContextSignedUrl: async (filename: string, contentType: string) => {
    const response = await apiClient.post('/api/scenes/context/signed-url', {
      filename,
      content_type: contentType,
    })
    return response.data
  },

  getPlaybackUrl: async (videoId: string) => {
    const response = await apiClient.get(`/api/scenes/${videoId}/playback-url`)
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
  listJobs: async (limit = 10, status?: string, cursor?: string) => {
    const response = await apiClient.get('/api/scenes/jobs', {
      params: { limit, status_filter: status, cursor },
    })
    return response.data as { items: any[]; next_cursor: string | null; has_more: boolean }
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

  archiveJob: async (jobId: string) => {
    const response = await apiClient.patch(`/api/scenes/jobs/${jobId}/archive`)
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

  getDownloadUrl: async (jobId: string, fileType: 'audio' | 'video' | 'vocals') => {
    const response = await apiClient.get(`/api/media/jobs/${jobId}/download/${fileType}`)
    return response.data as { url: string; gcs_path: string }
  },

  listVideos: async (limit = 10, cursor?: string) => {
    const response = await apiClient.get('/api/media/videos', {
      params: { limit, cursor },
    })
    return response.data as { items: any[]; next_cursor: string | null; has_more: boolean }
  },
}

// Image adaptation endpoints
export const imageApi = {
  createJob: async (data: {
    video_id: string
    prompt_id: string
    config: {
      aspect_ratios: string[]
      resolution: string
    }
  }) => {
    const response = await apiClient.post('/api/images/jobs', data)
    return response.data
  },

  getJob: async (jobId: string) => {
    const response = await apiClient.get(`/api/images/jobs/${jobId}`)
    return response.data
  },

  listJobsForAsset: async (assetId: string) => {
    const response = await apiClient.get(`/api/images/jobs/asset/${assetId}`)
    return response.data
  },

  getResults: async (jobId: string) => {
    const response = await apiClient.get(`/api/images/jobs/${jobId}/results`)
    return response.data
  },

  getSignedUrl: async (gcsPath: string) => {
    const response = await apiClient.post('/api/images/signed-url', null, {
      params: { gcs_path: gcsPath }
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

  createPrompt: async (data: {
    name: string
    type: string
    prompt_text: string
    schema_name?: string
    supports_context?: boolean
    context_description?: string
    response_type?: string | null
    response_schema?: Record<string, unknown> | null
  }) => {
    const response = await apiClient.post('/api/prompts', data)
    return response.data
  },

  updatePrompt: async (promptId: string, data: {
    name?: string
    type?: string
    prompt_text?: string
    schema_name?: string
    supports_context?: boolean
    context_description?: string
    response_type?: string | null
    response_schema?: Record<string, unknown> | null
  }) => {
    const response = await apiClient.put(`/api/prompts/${promptId}`, data)
    return response.data
  },

  deletePrompt: async (promptId: string) => {
    const response = await apiClient.delete(`/api/prompts/${promptId}`)
    return response.data
  },

  listSchemas: async () => {
    const response = await apiClient.get('/api/prompts/schemas')
    return response.data
  },

  listSchemasForCategory: async (category: string) => {
    const response = await apiClient.get(`/api/prompts/schemas/${category}`)
    return response.data
  },

  setSchema: async (category: string, data: { schema_name?: string; response_schema: Record<string, unknown> | null }) => {
    const response = await apiClient.put(`/api/prompts/schemas/${category}`, data)
    return response.data
  },

  deleteSchema: async (category: string, schemaName: string = 'default') => {
    const response = await apiClient.delete(`/api/prompts/schemas/${category}`, {
      params: { schema_name: schemaName },
    })
    return response.data
  },
}

// Search endpoints
export const searchApi = {
  getSyncStatus: async () => {
    const response = await apiClient.get('/api/search/sync-status')
    return response.data
  },

  syncResults: async (resultIds: string[], resync = false) => {
    const response = await apiClient.post('/api/search/sync', {
      result_ids: resultIds,
      resync,
    })
    return response.data
  },

  deleteSyncedResult: async (resultId: string) => {
    const response = await apiClient.delete(`/api/search/sync/${resultId}`)
    return response.data
  },

  searchVideos: async (
    query: string,
    limit = 20,
    audio?: string,
    audioMime?: string,
  ) => {
    const response = await apiClient.post('/api/search/videos', {
      query,
      limit,
      ...(audio ? { audio, audio_mime: audioMime } : {}),
    })
    return response.data
  },

  searchWithinVideo: async (videoId: string, query: string, limit = 20) => {
    const response = await apiClient.post(`/api/search/videos/${videoId}`, {
      query,
      limit,
    })
    return response.data
  },
}

// Branding endpoints
export const brandingApi = {
  getBranding: async () => {
    const response = await apiClient.get('/api/branding')
    return response.data
  },

  updateBranding: async (data: { app_title?: string; subtitle?: string; logo_url?: string }) => {
    const response = await apiClient.put('/api/branding', data)
    return response.data
  },
}

// Auth endpoints
export const authApi = {
  validate: async (code: string) => {
    const response = await apiClient.post('/api/auth/validate', { code })
    return response.data as { valid: boolean; is_master: boolean; is_admin: boolean }
  },

  listCodes: async () => {
    const response = await apiClient.get('/api/auth/codes')
    return response.data
  },

  createCode: async (data: {
    code: string
    label?: string
    is_admin?: boolean
    owner?: string
    expires_at?: string | null
  }) => {
    const response = await apiClient.post('/api/auth/codes', data)
    return response.data
  },

  updateCode: async (codeId: string, data: { label?: string; owner?: string }) => {
    const response = await apiClient.patch(`/api/auth/codes/${codeId}`, data)
    return response.data
  },

  revokeCode: async (codeId: string) => {
    const response = await apiClient.post(`/api/auth/codes/${codeId}/revoke`)
    return response.data
  },

  activateCode: async (codeId: string) => {
    const response = await apiClient.post(`/api/auth/codes/${codeId}/activate`)
    return response.data
  },

  deleteCode: async (codeId: string) => {
    await apiClient.delete(`/api/auth/codes/${codeId}`)
  },
}

// Engagement analysis endpoints
export const engagementApi = {
  getBarcSignedUrl: async (filename: string, contentType: string) => {
    const response = await apiClient.post('/api/engagement/signed-url', {
      filename,
      content_type: contentType,
    })
    return response.data as { signed_url: string; gcs_path: string; expires_in_minutes: number }
  },

  createJob: async (data: {
    video_id: string
    source_scene_job_id: string
    barc_gcs_path: string
    config?: Record<string, unknown>
  }) => {
    const response = await apiClient.post('/api/engagement/jobs', data)
    return response.data
  },

  getJob: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}`)
    return response.data
  },

  listJobsForVideo: async (videoId: string) => {
    const response = await apiClient.get(`/api/engagement/videos/${videoId}/jobs`)
    return response.data
  },

  listEligibleSourceJobs: async (videoId: string) => {
    const response = await apiClient.get(`/api/engagement/videos/${videoId}/scene-jobs`)
    return response.data
  },

  listAllEligibleSourceJobs: async (limit = 100) => {
    const response = await apiClient.get('/api/engagement/scene-jobs', { params: { limit } })
    return response.data
  },

  getTimeseries: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}/timeseries`)
    return response.data as {
      points: [number, number][]
      metrics: Record<string, [number, number][]>
      primary_metric?: string
      time_column?: string
      score_column?: string
    }
  },

  getEntities: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}/entities`)
    return response.data as Array<{
      name: string
      kind: string
      appearances: { start_sec: number; end_sec: number }[]
      mention_count: number
      avg_intensity?: number | null
    }>
  },

  getCues: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}/cues`)
    return response.data as Array<{
      start_sec: number
      end_sec: number
      text: string
      kind: string
      speaker: string
      sentiment?: string
    }>
  },

  getScenes: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}/scenes`)
    return response.data as Array<{
      chunk_index?: number
      start_sec: number | null
      end_sec: number | null
      title?: string
      summary: string
      location?: string
    }>
  },

  getMarkers: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}/markers`)
    return response.data as Array<{
      start_sec: number
      type: string
      label: string
      kind: 'moment' | 'beat'
    }>
  },

  getRecommendations: async (jobId: string) => {
    const response = await apiClient.get(`/api/engagement/jobs/${jobId}/recommendations`)
    return response.data as {
      headline: string
      do_more_of: Array<{
        recommendation: string
        rationale: string
        expected_lift: 'low' | 'medium' | 'high'
        evidence?: { entity?: string; delta_pct?: number; sample_size?: number; anchor_timestamps?: number[] }
      }>
      do_less_of: Array<{
        recommendation: string
        rationale: string
        expected_lift: 'low' | 'medium' | 'high'
        evidence?: { entity?: string; delta_pct?: number; sample_size?: number; anchor_timestamps?: number[] }
      }>
      per_minute_callouts: Array<{
        minute_index?: number
        minute_start_sec: number
        minute_end_sec: number
        avg_score?: number
        what_happened: string
        why_it_dipped: string
        alternative: string
      }>
    }
  },

  deleteJob: async (jobId: string) => {
    const response = await apiClient.delete(`/api/engagement/jobs/${jobId}`)
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
