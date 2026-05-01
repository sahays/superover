import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type {
  Avatar,
  AvatarLiveConfig,
  AvatarLiveToken,
  AvatarStyle,
  AvatarVoice,
} from '@/types/avatar'

const KEY = ['avatars'] as const

export const avatarsApi = {
  list: async (): Promise<Avatar[]> => {
    const res = await apiClient.get('/api/avatars')
    return res.data
  },
  get: async (id: string): Promise<Avatar> => {
    const res = await apiClient.get(`/api/avatars/${id}`)
    return res.data
  },
  create: async (data: {
    name: string
    style?: AvatarStyle
    persona_prompt?: string
    voice: AvatarVoice
    preset_name: string
    language?: string
    default_greeting?: string
    enable_grounding?: boolean
  }): Promise<Avatar> => {
    const res = await apiClient.post('/api/avatars', data)
    return res.data
  },
  update: async (
    id: string,
    data: Partial<Pick<Avatar, 'name' | 'style' | 'persona_prompt' | 'voice' | 'language' | 'default_greeting' | 'enable_grounding'>>,
  ): Promise<Avatar> => {
    const res = await apiClient.patch(`/api/avatars/${id}`, data)
    return res.data
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/avatars/${id}`)
  },
  liveConfig: async (id: string): Promise<AvatarLiveConfig> => {
    const res = await apiClient.get(`/api/avatars/${id}/live-config`)
    return res.data
  },
  liveToken: async (id: string): Promise<AvatarLiveToken> => {
    const res = await apiClient.post(`/api/avatars/${id}/live-token`)
    return res.data
  },
}

export function useAvatars() {
  return useQuery({ queryKey: KEY, queryFn: avatarsApi.list })
}

export function useAvatar(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => avatarsApi.get(id!),
    enabled: !!id,
  })
}

export function useCreateAvatar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: avatarsApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateAvatar(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof avatarsApi.update>[1]) => avatarsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY })
      qc.invalidateQueries({ queryKey: [...KEY, id] })
    },
  })
}

export function useDeleteAvatar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: avatarsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

// WS upgrades can't carry custom headers, so we mint a short-lived signed
// token over authenticated HTTP and present it on the WS query string.
export async function buildAvatarLiveUrl(avatarId: string): Promise<string> {
  const { token } = await avatarsApi.liveToken(avatarId)
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const qs = new URLSearchParams({ token }).toString()
  return `${proto}//${host}/api/avatars/${avatarId}/live?${qs}`
}
