// Curated search response shape — emitted by POST /api/search/videos.

export interface VideoSearchResult {
  video_id: string
  video_filename: string | null
  top_match_text: string
  score: number
  chunk_count: number
  timestamp_start: string | null
  timestamp_end: string | null
  description: string | null
  genre: string | null
  content_type: string | null
  mood: string | null
  setting: string | null
  actors: string[] | null
}

export interface SearchRecommendation {
  video_id: string
  video_filename: string | null
  gcs_path: string | null
  recommendation_type: 'full_video' | 'clip'
  title: string
  reason: string
  clip_start: string | null
  clip_end: string | null
  confidence: number
  tier?: 'best' | 'similar' | 'also_like'
}

export interface CuratedSearchResponse {
  response_text: string
  recommendations: SearchRecommendation[]
  raw_results: VideoSearchResult[]
  interpreted_query: string | null
}
