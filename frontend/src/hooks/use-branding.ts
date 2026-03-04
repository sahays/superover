import { useQuery } from '@tanstack/react-query'
import { brandingApi } from '@/lib/api-client'

export const BRANDING_QUERY_KEY = ['branding']

export const BRANDING_DEFAULTS = {
  app_title: 'Superover',
  subtitle: 'Video Analysis Platform',
  logo_url: '',
}

export interface BrandingData {
  app_title: string
  subtitle: string
  logo_url: string
  updated_at?: string | null
}

export function useBranding() {
  return useQuery<BrandingData>({
    queryKey: BRANDING_QUERY_KEY,
    queryFn: brandingApi.getBranding,
    staleTime: 5 * 60 * 1000,
    placeholderData: BRANDING_DEFAULTS,
  })
}
