'use client'

import { Video, VideoStatus } from '@/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw, Video as VideoIcon, Clock, CheckCircle, AlertCircle, Loader2, MoreVertical, Trash2 } from 'lucide-react'
import { formatBytes, formatDuration } from '@/lib/utils'
import Link from 'next/link'
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
      <Link href={`/video/${video.video_id}`}>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <CardTitle className="line-clamp-1 text-lg">
                {video.filename}
              </CardTitle>
              <CardDescription className="mt-1">
                {formatBytes(video.size_bytes)}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={video.status} />
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
            {video.metadata?.duration && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="h-4 w-4" />
                {formatDuration(video.metadata.duration)}
              </div>
            )}
            {video.error_message && (
              <div className="rounded-md bg-destructive/10 p-2 text-destructive">
                <p className="text-xs">{video.error_message}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Link>
    </Card>
  )
}

function StatusBadge({ status }: { status: VideoStatus }) {
  const config = {
    [VideoStatus.UPLOADED]: {
      icon: Clock,
      label: 'Uploaded',
      className: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    },
    [VideoStatus.EXTRACTING_METADATA]: {
      icon: Loader2,
      label: 'Extracting Metadata',
      className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
      animate: true,
    },
    [VideoStatus.EXTRACTING_AUDIO]: {
      icon: Loader2,
      label: 'Extracting Audio',
      className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
      animate: true,
    },
    [VideoStatus.COMPRESSING]: {
      icon: Loader2,
      label: 'Compressing',
      className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
      animate: true,
    },
    [VideoStatus.CHUNKING]: {
      icon: Loader2,
      label: 'Chunking',
      className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
      animate: true,
    },
    [VideoStatus.ANALYZING]: {
      icon: Loader2,
      label: 'Analyzing',
      className: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
      animate: true,
    },
    [VideoStatus.COMPLETED]: {
      icon: CheckCircle,
      label: 'Completed',
      className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
    },
    [VideoStatus.FAILED]: {
      icon: AlertCircle,
      label: 'Failed',
      className: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
    },
  }

  const statusConfig = config[status]
  const { icon: Icon, label, className } = statusConfig
  const animate = 'animate' in statusConfig ? statusConfig.animate : false

  return (
    <div className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${className}`}>
      <Icon className={`h-3.5 w-3.5 ${animate ? 'animate-spin' : ''}`} />
      {label}
    </div>
  )
}
