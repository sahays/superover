import { useState, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, Film, Clock } from 'lucide-react'
import { searchApi, videoApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { SearchResultCard } from '@/components/search/search-result-card'
import { parseTimestamp } from '@/components/search/video-search-player'

interface VideoSearchResult {
  video_id: string
  video_filename: string | null
  top_match_text: string
  score: number
  chunk_count: number
  timestamp_start: string | null
  timestamp_end: string | null
}

interface InVideoSearchResult {
  chunk_index: number | null
  text_content: string
  timestamp_start: string | null
  timestamp_end: string | null
  score: number
}

interface SyncStatusItem {
  result_id: string
  video_id: string
  video_filename: string | null
  synced: boolean
}

type SearchMode = 'videos' | 'in-video'

export default function SearchPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<SearchMode>('videos')
  const [query, setQuery] = useState('')
  const [selectedVideoId, setSelectedVideoId] = useState<string>('')
  const [videoResults, setVideoResults] = useState<VideoSearchResult[] | null>(null)
  const [inVideoResults, setInVideoResults] = useState<InVideoSearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)

  // Fetch synced videos for the video selector
  const { data: syncStatus } = useQuery<SyncStatusItem[]>({
    queryKey: ['search-sync-status'],
    queryFn: () => searchApi.getSyncStatus(),
  })

  // Deduplicate synced videos
  const syncedVideos = syncStatus
    ? Array.from(
        new Map(
          syncStatus
            .filter((s) => s.synced)
            .map((s) => [s.video_id, s])
        ).values()
      )
    : []

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return
    setSearching(true)

    try {
      if (mode === 'videos') {
        const results = await searchApi.searchVideos(query)
        setVideoResults(results)
        setInVideoResults(null)
      } else {
        if (!selectedVideoId) return
        const results = await searchApi.searchWithinVideo(selectedVideoId, query)
        setInVideoResults(results)
        setVideoResults(null)

        // Load video URL for player
        if (!videoUrl || videoUrl !== selectedVideoId) {
          try {
            const video = await videoApi.getVideo(selectedVideoId)
            const { signed_url } = await videoApi.getSignedUrl(
              video.filename,
              video.content_type || 'video/mp4'
            )
            setVideoUrl(signed_url)
          } catch {
            setVideoUrl(null)
          }
        }
      }
    } finally {
      setSearching(false)
    }
  }, [query, mode, selectedVideoId, videoUrl])

  const handleSeek = (timestampStart: string | null) => {
    const seconds = parseTimestamp(timestampStart)
    if (seconds != null && videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play().catch(() => {})
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Search</h1>
        <p className="text-muted-foreground mt-1">
          Semantic search across analyzed video content
        </p>
      </div>

      {/* Search Controls */}
      <Card className="mb-8">
        <CardContent className="p-6">
          <div className="flex flex-col gap-4">
            {/* Mode Toggle */}
            <div className="flex items-center gap-4">
              <Button
                variant={mode === 'videos' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setMode('videos')
                  setInVideoResults(null)
                }}
              >
                <Film className="mr-2 h-4 w-4" />
                All Videos
              </Button>
              <Button
                variant={mode === 'in-video' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setMode('in-video')
                  setVideoResults(null)
                }}
              >
                <Clock className="mr-2 h-4 w-4" />
                Within Video
              </Button>
            </div>

            {/* Video selector for in-video mode */}
            {mode === 'in-video' && (
              <Select value={selectedVideoId} onValueChange={setSelectedVideoId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a video to search within..." />
                </SelectTrigger>
                <SelectContent>
                  {syncedVideos.map((v) => (
                    <SelectItem key={v.video_id} value={v.video_id}>
                      {v.video_filename || v.video_id}
                    </SelectItem>
                  ))}
                  {syncedVideos.length === 0 && (
                    <SelectItem value="_none" disabled>
                      No synced videos available
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            )}

            {/* Search input */}
            <div className="flex gap-2">
              <Input
                placeholder="Describe what you're looking for..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1"
              />
              <Button
                onClick={handleSearch}
                disabled={
                  searching ||
                  !query.trim() ||
                  (mode === 'in-video' && !selectedVideoId)
                }
              >
                <Search className="mr-2 h-4 w-4" />
                {searching ? 'Searching...' : 'Search'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results: All Videos Mode */}
      {mode === 'videos' && videoResults && (
        <div>
          {videoResults.length > 0 ? (
            <>
              {/* Best Matches (distance < 1.0) */}
              {videoResults.filter((r) => r.score < 1.0).length > 0 && (
                <div className="mb-8">
                  <h2 className="text-lg font-semibold mb-4">
                    Best Matches
                  </h2>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {videoResults.filter((r) => r.score < 1.0).map((result) => (
                      <VideoResultCard key={result.video_id} result={result} onClick={() => navigate(`/scene/${result.video_id}`)} />
                    ))}
                  </div>
                </div>
              )}

              {/* Also Interested (distance >= 1.0) */}
              {videoResults.filter((r) => r.score >= 1.0).length > 0 && (
                <div>
                  <h2 className="text-sm font-medium text-muted-foreground mb-4">
                    You may also be interested in
                  </h2>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {videoResults.filter((r) => r.score >= 1.0).map((result) => (
                      <VideoResultCard key={result.video_id} result={result} secondary onClick={() => navigate(`/scene/${result.video_id}`)} />
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Search className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-semibold">No results found</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Try a different search query or sync more results.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Results: In-Video Mode */}
      {mode === 'in-video' && inVideoResults && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Video Player */}
          <div>
            {videoUrl ? (
              <video
                ref={videoRef}
                src={videoUrl}
                controls
                className="w-full rounded-lg"
              />
            ) : (
              <div className="flex items-center justify-center rounded-lg border bg-muted/30 p-12">
                <p className="text-sm text-muted-foreground">Loading video...</p>
              </div>
            )}
          </div>

          {/* Results List */}
          <div>
            <h2 className="text-lg font-semibold mb-4">
              {inVideoResults.length} moment(s) found
            </h2>
            {inVideoResults.length > 0 ? (
              <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                {inVideoResults.map((result, idx) => (
                  <SearchResultCard
                    key={idx}
                    text={result.text_content}
                    score={result.score}
                    timestamp={result.timestamp_start}
                    chunkIndex={result.chunk_index}
                    onClick={() => handleSeek(result.timestamp_start)}
                  />
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="py-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    No matching moments found in this video.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Empty state when no search has been performed */}
      {!videoResults && !inVideoResults && (
        <Card>
          <CardContent className="py-12 text-center">
            <Search className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-semibold">Search your video content</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Use natural language to find scenes, objects, dialogues, and more across your analyzed videos.
            </p>
            <CardDescription className="mt-4">
              Make sure to sync scene results first via the Search Sync page.
            </CardDescription>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function VideoResultCard({
  result,
  secondary,
  onClick,
}: {
  result: VideoSearchResult
  secondary?: boolean
  onClick: () => void
}) {
  return (
    <Card
      className={`cursor-pointer transition-colors hover:bg-muted/50 ${
        secondary ? 'opacity-75' : ''
      }`}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <p className="text-sm font-medium truncate mb-2">
          {result.video_filename || result.video_id}
        </p>
        <div className="flex items-center gap-2 mb-2">
          {result.timestamp_start && (
            <Badge variant="outline" className="text-xs">
              {result.timestamp_start}
            </Badge>
          )}
          {result.chunk_count > 1 && (
            <Badge variant="secondary" className="text-xs">
              {result.chunk_count} matches
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-3">
          {result.top_match_text}
        </p>
      </CardContent>
    </Card>
  )
}
