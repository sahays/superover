import * as React from 'react'
import { Video } from '@/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw, Video as VideoIcon, Clock, CheckCircle, AlertCircle, Loader2, MoreVertical, Trash2, Info } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { formatBytes, formatDuration } from '@/lib/utils'
import { Link } from 'react-router-dom'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { videoApi } from '@/lib/api-client'
import { useMutation } from '@tanstack/react-query'

interface VideoListProps {
  videos: Video[]
  isLoading: boolean
  onRefresh: () => void
}

export function VideoList({ videos, isLoading, onRefresh }: VideoListProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
            <p className="mt-4 text-sm text-muted-foreground">Loading videos...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (videos.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <VideoIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-semibold">No videos yet</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Upload your first video to get started
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Videos</h2>
        <Button onClick={onRefresh} variant="outline" size="sm">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {videos.map((video) => (
          <VideoCard key={video.video_id} video={video} onDelete={onRefresh} />
        ))}
      </div>
    </div>
  )
}

function VideoCard({ video, onDelete }: { video: Video; onDelete: () => void }) {
  const [showMetadata, setShowMetadata] = React.useState(false)

  // Debug logging
  React.useEffect(() => {
    console.log('Video Card Debug:', {
      video_id: video.video_id,
      filename: video.filename,
      metadata: video.metadata,
      duration: video.metadata?.duration,
      durationType: typeof video.metadata?.duration,
      video_width: video.metadata?.video?.width,
      video_height: video.metadata?.video?.height,
    })
  }, [video])

  const deleteMutation = useMutation({
    mutationFn: () => videoApi.deleteVideo(video.video_id),
    onSuccess: () => {
      onDelete()
    },
  })

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (confirm(`Are you sure you want to delete "${video.filename}"?`)) {
      deleteMutation.mutate()
    }
  }

  return (
    <Card className="relative transition hover:shadow-lg group">
      <Link to={`/scene/${video.video_id}`}>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <CardTitle className="line-clamp-1 text-lg">
                {video.filename}
              </CardTitle>
              <CardDescription className="mt-1">
                {video.size_bytes ? formatBytes(video.size_bytes) : 'Size unknown'}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.preventDefault()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                    disabled={deleteMutation.isPending}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {video.metadata && (
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setShowMetadata(true)
                      }}
                    >
                      <Info className="mr-2 h-4 w-4" />
                      View Details
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem
                    onClick={handleDelete}
                    className="text-destructive focus:text-destructive"
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            {(() => {
              const hasDuration = video.metadata?.duration &&
                                 typeof video.metadata.duration === 'number' &&
                                 video.metadata.duration > 0
              console.log('Duration check:', { hasDuration, duration: video.metadata?.duration })
              return hasDuration && video.metadata ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  {formatDuration(video.metadata.duration)}
                </div>
              ) : null
            })()}
            {(() => {
              const hasResolution = video.metadata?.video?.width &&
                                   video.metadata?.video?.height &&
                                   typeof video.metadata.video.width === 'number' &&
                                   typeof video.metadata.video.height === 'number'
              console.log('Resolution check:', {
                hasResolution,
                width: video.metadata?.video?.width,
                height: video.metadata?.video?.height
              })
              return hasResolution && video.metadata?.video ? (
                <div className="text-muted-foreground">
                  {video.metadata.video.width} × {video.metadata.video.height}
                </div>
              ) : null
            })()}
            {video.error_message && (
              <div className="rounded-md bg-destructive/10 p-2 text-destructive">
                <p className="text-xs">{video.error_message}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Link>

      {/* Metadata Dialog */}
      <Dialog open={showMetadata} onOpenChange={setShowMetadata}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Video Metadata</DialogTitle>
            <DialogDescription>{video.filename}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {video.metadata && (
              <pre className="rounded bg-slate-100 p-4 text-xs dark:bg-slate-800 overflow-x-auto">
                {JSON.stringify(video.metadata, null, 2)}
              </pre>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
