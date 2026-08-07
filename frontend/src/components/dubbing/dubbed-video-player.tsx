import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Volume2,
  Download,
  Languages,
  Check,
  Subtitles,
  FileText,
  Play,
  Pause,
  RotateCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { dubbingApi, videoApi } from '@/lib/api-client'
import { DubbingJob, DubbingTrackInfo, TimedDubbingSegment } from '@/lib/types'

interface DubbedVideoPlayerProps {
  job: DubbingJob
}

const LANGUAGE_FLAGS: Record<string, string> = {
  'hi-IN': '🇮🇳 Hindi',
  'en-US': '🇺🇸 English',
  'pt-BR': '🇧🇷 Portuguese',
  'es-ES': '🇪🇸 Spanish',
  'de-DE': '🇩🇪 German',
  original: '🎬 Original',
}

export function DubbedVideoPlayer({ job }: DubbedVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const availableLanguages = Object.keys(job.tracks || {})
  const defaultTrack = availableLanguages.length > 0 ? availableLanguages[0] : 'original'
  const [activeLanguage, setActiveLanguage] = useState<string>(defaultTrack)
  const [currentTime, setCurrentTime] = useState<number>(0)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [showSubtitles, setShowSubtitles] = useState<boolean>(true)

  // Fetch original video playback URL
  const { data: originalPlayback } = useQuery({
    queryKey: ['original-video-playback', job.video_id],
    queryFn: () => videoApi.getPlaybackUrl(job.video_id),
  })

  // Fetch dubbed video playback URL for active language
  const { data: dubbedPlayback } = useQuery({
    queryKey: ['dubbed-playback-url', job.job_id, activeLanguage],
    queryFn: () => dubbingApi.getPlaybackUrl(job.job_id, activeLanguage, 'video'),
    enabled: activeLanguage !== 'original' && !!job.tracks?.[activeLanguage],
  })

  // Active track information
  const activeTrackInfo: DubbingTrackInfo | undefined = job.tracks?.[activeLanguage]
  const currentSegments: TimedDubbingSegment[] = activeTrackInfo?.segments || []

  // Active spoken dialogue line at current playback time
  const currentDialogue = currentSegments.find(
    (seg) => currentTime >= seg.start_seconds && currentTime <= seg.end_seconds
  )

  // Switch video source while preserving playback position
  const handleTrackChange = (newLanguage: string) => {
    const prevTime = videoRef.current ? videoRef.current.currentTime : 0
    const wasPlaying = videoRef.current ? !videoRef.current.paused : false

    setActiveLanguage(newLanguage)

    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.currentTime = prevTime
        if (wasPlaying) {
          videoRef.current.play().catch(() => {})
        }
      }
    }, 150)
  }

  // Playback sync
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime)
    }

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)

    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
    }
  }, [])

  // Video source resolution
  const videoSrc =
    activeLanguage === 'original'
      ? originalPlayback?.signed_url
      : dubbedPlayback?.signed_url || originalPlayback?.signed_url

  return (
    <div className="space-y-6">
      {/* Video Player & Dynamic Controls */}
      <Card className="overflow-hidden border-border bg-card/60 backdrop-blur-md">
        <div className="relative aspect-video bg-black flex items-center justify-center">
          {videoSrc ? (
            <video
              ref={videoRef}
              src={videoSrc}
              controls
              playsInline
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="text-center p-8 text-muted-foreground">
              <Languages className="h-12 w-12 mx-auto mb-2 opacity-50 animate-pulse" />
              <p>Preparing video stream...</p>
            </div>
          )}

          {/* Real-time Subtitle Overlay */}
          {showSubtitles && currentDialogue && (
            <div className="absolute bottom-16 left-0 right-0 px-6 text-center pointer-events-none transition-all">
              <span className="inline-block bg-black/80 text-white font-medium px-4 py-2 rounded-lg text-sm sm:text-base backdrop-blur-md shadow-lg border border-white/10 max-w-xl">
                {currentDialogue.translated_text || currentDialogue.original_text}
              </span>
            </div>
          )}
        </div>

        {/* Audio Track Switcher Toolbar */}
        <CardContent className="p-4 border-t bg-muted/20">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Volume2 className="h-4 w-4 text-primary" />
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Dubbing Audio Track:
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                variant={activeLanguage === 'original' ? 'default' : 'outline'}
                size="sm"
                className="h-8 text-xs gap-1.5"
                onClick={() => handleTrackChange('original')}
              >
                {LANGUAGE_FLAGS['original']}
                {activeLanguage === 'original' && <Check className="h-3 w-3" />}
              </Button>

              {availableLanguages.map((lang) => (
                <Button
                  key={lang}
                  variant={activeLanguage === lang ? 'default' : 'outline'}
                  size="sm"
                  className="h-8 text-xs gap-1.5"
                  onClick={() => handleTrackChange(lang)}
                >
                  {LANGUAGE_FLAGS[lang] || lang}
                  {activeLanguage === lang && <Check className="h-3 w-3" />}
                </Button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={showSubtitles ? 'secondary' : 'ghost'}
                size="sm"
                className="h-8 text-xs gap-1.5"
                onClick={() => setShowSubtitles(!showSubtitles)}
              >
                <Subtitles className="h-3.5 w-3.5" />
                <span>{showSubtitles ? 'Subtitles ON' : 'Subtitles OFF'}</span>
              </Button>

              {dubbedPlayback?.signed_url && (
                <a href={dubbedPlayback.signed_url} download={`dubbed_${activeLanguage}.mp4`} target="_blank" rel="noreferrer">
                  <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5">
                    <Download className="h-3.5 w-3.5" />
                    <span>Download MP4</span>
                  </Button>
                </a>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Script & Dialogue Comparison Drawer */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg font-heading flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
                Dubbing Script & Multimodal Timeline
              </CardTitle>
              <CardDescription>
                Synchronized line-by-line comparison between original and translated speech.
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-xs">
              {currentSegments.length} Translated Turn(s)
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {currentSegments.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No dialogue segments extracted for this track yet.
            </p>
          ) : (
            <div className="divide-y max-h-96 overflow-y-auto rounded-md border border-border">
              {currentSegments.map((seg, idx) => {
                const isActive = currentTime >= seg.start_seconds && currentTime <= seg.end_seconds
                return (
                  <div
                    key={idx}
                    onClick={() => {
                      if (videoRef.current) {
                        videoRef.current.currentTime = seg.start_seconds
                        videoRef.current.play().catch(() => {})
                      }
                    }}
                    className={`p-3 text-xs sm:text-sm cursor-pointer transition-colors flex items-start gap-4 ${
                      isActive ? 'bg-primary/15 font-medium' : 'hover:bg-muted/40'
                    }`}
                  >
                    <div className="shrink-0 font-mono text-[11px] text-muted-foreground mt-0.5 w-20">
                      {seg.start_seconds.toFixed(1)}s - {seg.end_seconds.toFixed(1)}s
                    </div>

                    <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-muted-foreground block mb-0.5">
                          Original ({seg.speaker || 'Speaker'})
                        </span>
                        <p className="text-muted-foreground italic">{seg.original_text}</p>
                      </div>

                      <div>
                        <span className="text-[10px] uppercase font-semibold text-primary block mb-0.5">
                          {LANGUAGE_FLAGS[activeLanguage] || 'Translated'}
                        </span>
                        <p className="text-foreground">{seg.translated_text}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
