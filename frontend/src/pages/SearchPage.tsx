import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Film,
  Clock,
  Sparkles,
  Play,
  Star,
  Mic,
  Square,
} from 'lucide-react'
import { searchApi, videoApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  VideoSearchPlayer,
  parseTimestamp,
} from '@/components/search/video-search-player'
import { useAudioRecorder } from '@/hooks/use-audio-recorder'

const LOADING_MESSAGES = [
  'Asking the AI to binge-watch your videos real quick...',
  'Teaching robots to appreciate cinematography...',
  'Scanning every pixel with superhuman patience...',
  'Our AI intern is reviewing the footage...',
  'Convincing Gemini your videos are worth watching...',
  'Speed-watching at 1,000,000x... almost there...',
  'Cross-referencing scenes with impeccable taste...',
  'Summoning the video oracle for your query...',
  'Polishing the crystal ball of search results...',
  'Running through your footage in flip-flops...',
]

interface VideoSearchResult {
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

interface SearchRecommendation {
  video_id: string
  video_filename: string | null
  gcs_path: string | null
  recommendation_type: 'full_video' | 'clip'
  title: string
  reason: string
  clip_start: string | null
  clip_end: string | null
  confidence: number
}

interface CuratedSearchResponse {
  response_text: string
  recommendations: SearchRecommendation[]
  raw_results: VideoSearchResult[]
  interpreted_query: string | null
}

function SearchLoadingAnimation() {
  const [messageIndex, setMessageIndex] = useState(() =>
    Math.floor(Math.random() * LOADING_MESSAGES.length)
  )

  useEffect(() => {
    const scheduleNext = () => {
      const delay = 2000 + Math.random() * 2000 // 2-4 seconds
      return setTimeout(() => {
        setMessageIndex((prev) => {
          let next: number
          do {
            next = Math.floor(Math.random() * LOADING_MESSAGES.length)
          } while (next === prev && LOADING_MESSAGES.length > 1)
          return next
        })
        timerId = scheduleNext()
      }, delay)
    }
    let timerId = scheduleNext()
    return () => clearTimeout(timerId)
  }, [])

  const message = LOADING_MESSAGES[messageIndex]
  const words = message.split(' ')

  return (
    <Card>
      <CardContent className="py-16 text-center">
        <Sparkles className="mx-auto h-10 w-10 text-primary mb-6 animate-pulse" />
        <p className="text-lg leading-relaxed">
          {words.map((word, i) => (
            <span
              key={`${messageIndex}-${i}`}
              className="inline-block animate-glow-word mx-1"
              style={{ animationDelay: `${i * 0.12}s` }}
            >
              {word}
            </span>
          ))}
        </p>
      </CardContent>
    </Card>
  )
}

export default function SearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [curatedResponse, setCuratedResponse] =
    useState<CuratedSearchResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchDuration, setSearchDuration] = useState<number | null>(null)

  const {
    isRecording,
    audioBase64,
    secondsLeft,
    error: micError,
    startRecording,
    stopRecording,
    reset: resetAudio,
  } = useAudioRecorder(10_000)

  const handleSearch = useCallback(
    async (audio?: string, audioMime?: string) => {
      if (!query.trim() && !audio) return
      setSearching(true)
      setSearchDuration(null)
      const startTime = performance.now()

      try {
        const response = await searchApi.searchVideos(
          query,
          20,
          audio,
          audioMime,
        )
        setCuratedResponse(response)
      } finally {
        setSearchDuration(
          Math.round((performance.now() - startTime) / 100) / 10,
        )
        setSearching(false)
      }
    },
    [query],
  )

  // Auto-submit when recording completes
  useEffect(() => {
    if (!isRecording && audioBase64) {
      handleSearch(audioBase64, 'audio/webm')
      resetAudio()
    }
  }, [isRecording, audioBase64, handleSearch, resetAudio])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const handleMicClick = () => {
    if (isRecording) {
      stopRecording()
    } else {
      resetAudio()
      startRecording()
    }
  }

  // Split recommendations by confidence
  const { bestMatches, alsoLike } = useMemo(() => {
    if (!curatedResponse) return { bestMatches: [], alsoLike: [] }
    const best: SearchRecommendation[] = []
    const also: SearchRecommendation[] = []
    for (const rec of curatedResponse.recommendations) {
      if (rec.confidence >= 0.85) best.push(rec)
      else if (rec.confidence >= 0.60) also.push(rec)
    }
    return { bestMatches: best, alsoLike: also }
  }, [curatedResponse])

  const totalResults = bestMatches.length + alsoLike.length

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Search</h1>
        <p className="text-muted-foreground mt-1">
          AI-powered semantic search across analyzed video content
        </p>
      </div>

      {/* Search Bar */}
      <div className="flex gap-2 mb-8">
        <Input
          placeholder="Describe what you're looking for (any language)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1"
        />
        <Button
          variant={isRecording ? 'destructive' : 'outline'}
          size="icon"
          onClick={handleMicClick}
          disabled={searching}
          title={isRecording ? 'Stop recording' : 'Voice search'}
        >
          {isRecording ? (
            <Square className="h-4 w-4" />
          ) : (
            <Mic className="h-4 w-4" />
          )}
        </Button>
        <Button
          onClick={() => handleSearch()}
          disabled={searching || !query.trim()}
        >
          <Search className="mr-2 h-4 w-4" />
          {searching ? 'Searching...' : 'Search'}
        </Button>
      </div>

      {/* Recording indicator */}
      {isRecording && (
        <div className="flex items-center gap-2 mb-4 text-sm text-destructive">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-destructive" />
          </span>
          Recording{secondsLeft != null ? ` (${secondsLeft}s remaining)` : ''}...
        </div>
      )}

      {/* Mic error */}
      {micError && (
        <p className="text-sm text-destructive mb-4">{micError}</p>
      )}

      {/* Loading Animation */}
      {searching && <SearchLoadingAnimation />}

      {/* Results */}
      {!searching && curatedResponse && (
        <div className="space-y-6">
          {/* Results summary */}
          {searchDuration != null && totalResults > 0 && (
            <p className="text-sm text-muted-foreground">
              Found {totalResults} result{totalResults !== 1 ? 's' : ''} in{' '}
              {searchDuration}s
            </p>
          )}

          {/* Interpreted query */}
          {curatedResponse.interpreted_query && (
            <p className="text-sm text-muted-foreground italic">
              Searched for: &ldquo;{curatedResponse.interpreted_query}&rdquo;
            </p>
          )}

          {/* Best Matches */}
          {bestMatches.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4">Best Matches</h2>
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                {bestMatches.map((rec, idx) => (
                  <RecommendationCard
                    key={`${rec.video_id}-best-${idx}`}
                    recommendation={rec}
                    onClick={() => navigate(`/scene/${rec.video_id}`)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* You May Also Like */}
          {alsoLike.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 text-muted-foreground">
                You May Also Like
              </h2>
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                {alsoLike.map((rec, idx) => (
                  <RecommendationCard
                    key={`${rec.video_id}-also-${idx}`}
                    recommendation={rec}
                    secondary
                    onClick={() => navigate(`/scene/${rec.video_id}`)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* No results */}
          {curatedResponse.recommendations.length === 0 && (
            <Card>
              <CardContent className="py-12 text-center">
                <Search className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-semibold">
                  No results found
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Try a different search query or sync more results.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Empty state when no search has been performed */}
      {!searching && !curatedResponse && (
        <Card>
          <CardContent className="py-12 text-center">
            <Search className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-semibold">
              Search your video content
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Use natural language to find scenes, objects, dialogues, and more
              across your analyzed videos.
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

function RecommendationCard({
  recommendation,
  secondary,
}: {
  recommendation: SearchRecommendation
  secondary?: boolean
  onClick: () => void
}) {
  const isClip = recommendation.recommendation_type === 'clip'
  const [playingClip, setPlayingClip] = useState(false)
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null)
  const clipVideoRef = useRef<HTMLVideoElement>(null)
  const endTimeRef = useRef<number | null>(null)

  const startPlayback = async () => {
    if (!playbackUrl) {
      try {
        const { signed_url } = await videoApi.getPlaybackUrl(recommendation.video_id)
        setPlaybackUrl(signed_url)
      } catch {
        return
      }
    }
    setPlayingClip(true)
  }

  const handleVideoLoaded = () => {
    if (!clipVideoRef.current) return
    if (isClip && recommendation.clip_start) {
      const startSec = parseTimestamp(recommendation.clip_start)
      if (startSec != null) {
        clipVideoRef.current.currentTime = startSec
      }
      endTimeRef.current = parseTimestamp(recommendation.clip_end)
    }
    clipVideoRef.current.play().catch(() => {})
  }

  const handleTimeUpdate = () => {
    if (
      clipVideoRef.current &&
      endTimeRef.current != null &&
      clipVideoRef.current.currentTime >= endTimeRef.current
    ) {
      clipVideoRef.current.pause()
    }
  }

  return (
    <Card
      className={`overflow-hidden flex flex-col ${secondary ? 'opacity-80' : ''}`}
    >
      {/* Video Player — natural aspect ratio, capped height */}
      <div className="relative w-full bg-black">
        {playingClip && playbackUrl ? (
          <video
            ref={clipVideoRef}
            src={playbackUrl}
            controls
            onLoadedMetadata={handleVideoLoaded}
            onTimeUpdate={handleTimeUpdate}
            className="w-full max-h-64 object-contain"
          />
        ) : (
          <>
            <VideoSearchPlayer
              videoId={recommendation.video_id}
              className="object-contain max-h-64"
            />
            {isClip && recommendation.clip_start && (
              <button
                onClick={startPlayback}
                className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/40 transition-colors group"
              >
                <div className="rounded-full bg-white/90 p-3 group-hover:scale-110 transition-transform">
                  <Play className="h-6 w-6 text-black fill-black" />
                </div>
              </button>
            )}
          </>
        )}
      </div>

      <CardContent className="p-4 space-y-2 flex-1 flex flex-col min-h-0">
        {/* Title + type badge */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold line-clamp-1">
            {recommendation.title}
          </p>
          <Badge
            variant={isClip ? 'secondary' : 'default'}
            className="text-xs shrink-0 cursor-pointer hover:opacity-80"
            onClick={startPlayback}
          >
            {isClip ? (
              <>
                <Play className="mr-1 h-3 w-3" />
                Clip
              </>
            ) : (
              <>
                <Film className="mr-1 h-3 w-3" />
                Full Video
              </>
            )}
          </Badge>
        </div>

        {/* Filename */}
        {recommendation.video_filename && (
          <p className="text-xs text-muted-foreground truncate">
            {recommendation.video_filename}
          </p>
        )}

        {/* Reason */}
        <p className="text-sm text-muted-foreground line-clamp-3 flex-1">
          {recommendation.reason}
        </p>

        {/* Clip timestamps + confidence */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {isClip && recommendation.clip_start && (
            <button
              onClick={startPlayback}
              className="flex items-center gap-1 hover:text-foreground transition-colors"
            >
              <Clock className="h-3 w-3" />
              <span>
                {recommendation.clip_start}
                {recommendation.clip_end && ` - ${recommendation.clip_end}`}
              </span>
            </button>
          )}
          <div className="flex items-center gap-1">
            <Star className="h-3 w-3" />
            <span>{Math.round(recommendation.confidence * 100)}% match</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
