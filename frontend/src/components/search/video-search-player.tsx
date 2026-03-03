import { useRef, useCallback, useEffect, useState } from 'react'
import { videoApi } from '@/lib/api-client'

interface VideoSearchPlayerProps {
  videoId: string
}

export function VideoSearchPlayer({ videoId }: VideoSearchPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadVideo() {
      try {
        const video = await videoApi.getVideo(videoId)
        if (cancelled) return

        // Get a signed URL for the video's GCS path
        const { signed_url } = await videoApi.getSignedUrl(
          video.filename,
          video.content_type || 'video/mp4'
        )
        if (!cancelled) {
          setVideoUrl(signed_url)
        }
      } catch {
        if (!cancelled) {
          setError('Failed to load video')
        }
      }
    }

    loadVideo()
    return () => {
      cancelled = true
    }
  }, [videoId])

  const seekTo = useCallback((seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play().catch(() => {
        // Autoplay may be blocked; that's fine
      })
    }
  }, [])

  if (error) {
    return (
      <div className="flex items-center justify-center rounded-lg border bg-muted/30 p-8">
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    )
  }

  if (!videoUrl) {
    return (
      <div className="flex items-center justify-center rounded-lg border bg-muted/30 p-8">
        <p className="text-sm text-muted-foreground">Loading video...</p>
      </div>
    )
  }

  return (
    <div>
      <video
        ref={videoRef}
        src={videoUrl}
        controls
        className="w-full rounded-lg"
      />
      {/* Expose seekTo via a data attribute for parent access */}
      <div data-seek-to="" ref={(el) => {
        if (el) {
          (el as HTMLDivElement & { seekTo: (s: number) => void }).seekTo = seekTo
        }
      }} className="hidden" />
    </div>
  )
}

// Helper to parse timestamp string like "00:01:30" to seconds
export function parseTimestamp(ts: string | null | undefined): number | null {
  if (!ts) return null
  const parts = ts.split(':').map(Number)
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2]
  }
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1]
  }
  const n = Number(ts)
  return isNaN(n) ? null : n
}
