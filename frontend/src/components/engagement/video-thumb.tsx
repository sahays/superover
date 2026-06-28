import { useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Film } from 'lucide-react'
import { videoApi } from '@/lib/api-client'
import { cn } from '@/lib/utils'

interface VideoThumbProps {
  videoId: string
  className?: string
}

/**
 * Lightweight inline video preview for list cards. Reuses the signed playback
 * URL (no thumbnail generation): seeks to ~2s for a poster frame, plays muted
 * on hover, resets on leave.
 */
export function VideoThumb({ videoId, className }: VideoThumbProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  const { data, isError } = useQuery({
    queryKey: ['playback-url', videoId],
    queryFn: () => videoApi.getPlaybackUrl(videoId) as Promise<{ signed_url: string }>,
    staleTime: 50 * 60_000, // signed URLs last ~60min
    retry: 1,
  })

  const url = data?.signed_url

  if (isError || (!url && data)) {
    return (
      <div
        className={cn(
          'flex aspect-video w-full items-center justify-center rounded-md bg-muted',
          className
        )}
      >
        <Film className="h-6 w-6 text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className={cn('relative aspect-video w-full overflow-hidden rounded-md bg-muted', className)}>
      {url && (
        <video
          ref={videoRef}
          src={`${url}#t=2`}
          muted
          loop
          playsInline
          preload="metadata"
          className="h-full w-full object-cover"
          onMouseEnter={() => videoRef.current?.play().catch(() => {})}
          onMouseLeave={() => {
            const v = videoRef.current
            if (v) {
              v.pause()
              v.currentTime = 2
            }
          }}
        />
      )}
    </div>
  )
}
