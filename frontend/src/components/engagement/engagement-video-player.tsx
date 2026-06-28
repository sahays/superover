import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { videoApi } from '@/lib/api-client'
import { cn } from '@/lib/utils'

export interface EngagementVideoPlayerHandle {
  /** Seek the player to `seconds` and start playback. */
  seekTo: (seconds: number) => void
}

interface Props {
  videoId: string
  className?: string
  /** Fires as playback progresses (≈4Hz) so the page playhead can follow. */
  onTime?: (seconds: number) => void
}

/**
 * Controllable player for the engagement detail page. Exposes an imperative
 * `seekTo` so peak/valley, callout, and chart clicks can jump the video.
 * Reuses the existing signed playback URL — no backend changes.
 */
export const EngagementVideoPlayer = forwardRef<EngagementVideoPlayerHandle, Props>(
  function EngagementVideoPlayer({ videoId, className, onTime }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null)
    const [url, setUrl] = useState<string | null>(null)
    const [error, setError] = useState(false)

    useEffect(() => {
      let cancelled = false
      videoApi
        .getPlaybackUrl(videoId)
        .then((d: { signed_url: string }) => {
          if (!cancelled) setUrl(d.signed_url)
        })
        .catch(() => {
          if (!cancelled) setError(true)
        })
      return () => {
        cancelled = true
      }
    }, [videoId])

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        const v = videoRef.current
        if (!v) return
        // Position-and-pause: move the playhead to the clicked moment and keep it
        // there. Auto-playing made the playhead drift off independently after a
        // click; the user resumes with the native play control (which re-engages
        // live follow via onTimeUpdate).
        v.pause()
        v.currentTime = seconds
        v.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      },
    }))

    if (error) {
      return (
        <div className="flex aspect-video items-center justify-center rounded-lg border bg-muted/30">
          <p className="text-sm text-muted-foreground">Video unavailable</p>
        </div>
      )
    }

    if (!url) {
      return (
        <div className="flex aspect-video items-center justify-center rounded-lg border bg-muted/30">
          <p className="text-sm text-muted-foreground">Loading video…</p>
        </div>
      )
    }

    return (
      <video
        ref={videoRef}
        src={url}
        controls
        preload="metadata"
        onTimeUpdate={onTime ? (e) => onTime((e.target as HTMLVideoElement).currentTime) : undefined}
        className={cn('aspect-video w-full rounded-lg bg-black', className)}
      />
    )
  }
)
