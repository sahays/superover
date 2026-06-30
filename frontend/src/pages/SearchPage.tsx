import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import {
  Search,
  Film,
  Clock,
  Sparkles,
  Play,
  Star,
  Mic,
  Square,
  Sword,
  ShoppingCart,
  Music,
  Trophy,
  Heart,
  Languages,
  Clapperboard,
} from 'lucide-react'
import { searchApi, videoApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { parseTimestamp } from '@/components/search/video-search-player'
import { useAudioRecorder } from '@/hooks/use-audio-recorder'
import { useAuthStore } from '@/store/useAuthStore'
import { AvatarSearchPanel } from '@/components/search/avatar-search-panel'
import type { CuratedSearchResponse, SearchRecommendation } from '@/types/search'

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
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { isMaster, isAdmin } = useAuthStore()
  const elevated = isMaster || isAdmin
  const [query, setQuery] = useState('')
  const [curatedResponse, setCuratedResponse] =
    useState<CuratedSearchResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchDuration, setSearchDuration] = useState<number | null>(null)
  // Avatar mode is now URL-driven: `/search/avatar` enables it, `/search`
  // disables it. The optional `?avatar=<id>` query param picks a specific
  // avatar when more than one exists.
  const avatarMode = location.pathname === '/search/avatar'
  const selectedAvatarId = searchParams.get('avatar')
  const hasSearchedRef = useRef(false)

  const handleSelectAvatar = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams)
      params.set('avatar', id)
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const toggleAvatarMode = () => {
    if (avatarMode) navigate('/search')
    else navigate('/search/avatar')
  }

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
        hasSearchedRef.current = true
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
      setQuery('')
      hasSearchedRef.current = false
      resetAudio()
      startRecording()
    }
  }

  const sampleSearchGroups = [
    {
      label: 'Example searches',
      searches: [
        { icon: Sword, text: 'I am in the mood for some action movies today' },
        { icon: Heart, text: 'I am heartbroken, can you suggest some action or comedy movies' },
        { icon: Languages, text: 'मैं बहुत दुखी महसूस कर रहा हूँ, क्या आप कुछ एक्शन या कॉमेडी फिल्मों के सुझाव दे सकते हैं?' },
      ],
    },
    {
      label: 'Find clips in videos',
      searches: [
        { icon: ShoppingCart, text: 'Show me clips where people are haggling' },
        { icon: Music, text: 'Amaze me with some cool dance moves' },
        { icon: Trophy, text: 'Free kick in a soccer match' },
        { icon: Clapperboard, text: 'आप मुझे वो सीन दिखाइये जहाँ टोनी स्टार्क उदास बैठा है स्पेस में' },
        { icon: Heart, text: 'Kiara Advani in pink saree' },
      ],
    },
  ]

  // Trigger search when query is set from a sample pill
  const pendingSearchRef = useRef(false)

  const handleSampleSearch = useCallback(
    (text: string) => {
      setQuery(text)
      pendingSearchRef.current = true
    },
    [],
  )

  useEffect(() => {
    if (pendingSearchRef.current && query) {
      pendingSearchRef.current = false
      handleSearch()
    }
  }, [query, handleSearch])

  // Recommendations arrive already ranked by relevance (closest BQ matches
  // first). Present the top few as "Best Matches" and the remainder as "You May
  // Also Like" — a rank-based split, since the deterministic relevance score is
  // not on the same calibrated scale the old LLM-curator confidence was.
  const { bestMatches, alsoLike } = useMemo<{
    bestMatches: SearchRecommendation[]
    alsoLike: SearchRecommendation[]
  }>(() => {
    if (!curatedResponse) return { bestMatches: [], alsoLike: [] }
    const recs = curatedResponse.recommendations
    return { bestMatches: recs.slice(0, 3), alsoLike: recs.slice(3) }
  }, [curatedResponse])

  const totalResults = bestMatches.length + alsoLike.length

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Avatar mode corner widget — only renders when toggle is on. */}
      {avatarMode && (
        <div className="fixed top-20 right-6 z-30">
          <AvatarSearchPanel
            avatarId={selectedAvatarId}
            onSelectAvatar={handleSelectAvatar}
            onResults={setCuratedResponse}
            onSearchingChange={setSearching}
            onDuration={setSearchDuration}
          />
        </div>
      )}

      {/* Page Header */}
      <div className="mb-8 animate-slide-up">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold font-heading">Conversational Search</h1>
          {elevated && (
            <button
              type="button"
              onClick={toggleAvatarMode}
              className={`shrink-0 inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                avatarMode
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-muted-foreground/30 text-muted-foreground hover:border-primary/40 hover:text-foreground'
              }`}
              aria-pressed={avatarMode}
              title={avatarMode ? 'Disable Avatar mode' : 'Enable Avatar mode'}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Avatar mode {avatarMode ? 'on' : 'off'}
            </button>
          )}
        </div>
        <p className="text-muted-foreground mt-1 flex items-center gap-2 flex-wrap">
          <span>Powered by</span>
          <img src="/gemini-logo.svg" alt="Gemini" className="h-5 inline-block dark:invert" />
          <span>&amp;</span>
          <img src="/bigquery-logo.svg" alt="BigQuery" className="h-5 inline-block" />
          <span>BigQuery</span>
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Film className="h-3.5 w-3.5" />
            Seamless full video and clips search
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Languages className="h-3.5 w-3.5" />
            Conversational voice and text search in 50+ languages
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Don&apos;t fight the search box, find what you are looking for
          </span>
        </div>
      </div>

      {/* Search Bar — hidden in avatar mode (the avatar takes input). */}
      {!avatarMode && (
      <div className="input-glow rounded-xl border-2 border-primary/30 p-2 card-surface animate-slide-up flex gap-2 mb-8 shadow-lg shadow-primary/5">
        <Input
          placeholder="Describe what you're looking for (any language)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (hasSearchedRef.current) {
              setQuery('')
              hasSearchedRef.current = false
            }
          }}
          className="flex-1 border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 text-base h-11"
        />
        <Button
          variant={isRecording ? 'destructive' : 'outline'}
          size="icon"
          onClick={handleMicClick}
          disabled={searching}
          title={isRecording ? 'Stop recording' : 'Voice search'}
          className="btn-icon-spring"
        >
          {isRecording ? (
            <span className="btn-icon"><Square className="h-4 w-4" /></span>
          ) : (
            <span className="btn-icon"><Mic className="h-4 w-4" /></span>
          )}
        </Button>
        <Button
          onClick={() => handleSearch()}
          disabled={searching || !query.trim()}
          className="btn-primary"
        >
          <Search className="mr-2 h-4 w-4" />
          {searching ? 'Searching...' : 'Search'}
        </Button>
      </div>
      )}

      {/* Recording indicator */}
      {!avatarMode && isRecording && (
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
            <p className="text-sm text-muted-foreground animate-fade-in">
              Found <span className="font-mono">{totalResults}</span> result{totalResults !== 1 ? 's' : ''} in{' '}
              <span className="font-mono">{searchDuration}s</span>
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
            <div className="animate-slide-up">
              <h2 className="text-lg font-semibold font-heading mb-4 line-sweep">Best Matches</h2>
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 stagger-children">
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
            <div className="animate-slide-up">
              <h2 className="text-lg font-semibold font-heading mb-4 text-muted-foreground line-sweep">
                You May Also Like
              </h2>
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 stagger-children">
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
            <Card className="animate-spring-in">
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

          {/* Sample searches after results — hidden in avatar mode */}
          {!avatarMode && (
            <SampleSearchPills groups={sampleSearchGroups} onSelect={handleSampleSearch} />
          )}
        </div>
      )}

      {/* Empty state when no search has been performed */}
      {!searching && !curatedResponse && !avatarMode && (
        <div className="space-y-6 animate-fade-in">
          <SampleSearchPills groups={sampleSearchGroups} onSelect={handleSampleSearch} />
        </div>
      )}

      {/* Empty state in avatar mode — minimal coaching while waiting for voice. */}
      {!searching && !curatedResponse && avatarMode && (
        <div className="text-center text-sm text-muted-foreground py-12 animate-fade-in">
          Talk to the avatar — describe a movie, mood, or scene. Results will appear here.
        </div>
      )}
    </div>
  )
}

function SampleSearchPills({
  groups,
  onSelect,
}: {
  groups: { label: string; searches: { icon: React.ElementType; text: string }[] }[]
  onSelect: (text: string) => void
}) {
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="text-sm font-medium text-muted-foreground mb-3">{group.label}</p>
          <div className="flex flex-wrap gap-2 stagger-children">
            {group.searches.map((sample) => {
              const Icon = sample.icon
              return (
                <button
                  key={sample.text}
                  onClick={() => onSelect(sample.text)}
                  className="group badge-glow btn-press inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-accent/50 transition-colors"
                >
                  <Icon className="h-4 w-4 shrink-0 group-hover:text-primary transition-colors" />
                  <span className="line-clamp-1">{sample.text}</span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
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
      className={`card-interactive relative overflow-hidden flex flex-col ${secondary ? 'opacity-80' : ''}`}
    >
      <div className={`absolute top-0 right-0 w-24 h-24 bg-gradient-to-br ${secondary ? 'from-sky-500/10' : 'from-orange-500/10'} to-transparent rounded-bl-full pointer-events-none`} />
      {/* Video Player — lazily mounted. We render only a lightweight placeholder
          until the user clicks play; the <video> element and its playback-URL
          fetch are created on demand. Eagerly mounting a <video> per card (up to
          20 at once, each with a network fetch) janks the main thread for ~1s,
          which in Avatar mode starves the live avatar's WebCodecs decode/draw
          and audio scheduling — freezing it mid-utterance. */}
      <div className="relative w-full bg-black aspect-video">
        {playingClip && playbackUrl ? (
          <video
            ref={clipVideoRef}
            src={playbackUrl}
            controls
            autoPlay
            onLoadedMetadata={handleVideoLoaded}
            onTimeUpdate={handleTimeUpdate}
            className="w-full h-full object-contain"
          />
        ) : (
          <button
            onClick={startPlayback}
            className="absolute inset-0 flex items-center justify-center bg-black hover:bg-black/80 transition-colors group"
            title="Play"
          >
            <div className="rounded-full bg-white/90 p-3 group-hover:scale-110 transition-transform">
              <Play className="h-6 w-6 text-black fill-black" />
            </div>
          </button>
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
            className="text-xs shrink-0 cursor-pointer hover:opacity-80 badge-glow"
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
            <span className="font-mono">{Math.round(recommendation.confidence * 100)}%</span> match
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
