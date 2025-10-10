'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Video, FileVideo, CheckCircle, ExternalLink, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { mediaApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatBytes, formatDuration } from '@/lib/utils'
import { MediaJobStatus, type MediaJob } from '@/lib/types'

interface VideoPickerProps {
  onSelect: (videoId: string, isCompressed: boolean, gcsPath: string, chunkDuration: number) => void
  onCancel: () => void
}

export interface VideoWithJobs {
  video_id: string
  filename: string
  gcs_path: string
  size_bytes?: number
  metadata?: {
    duration?: number
    video?: {
      width?: number
      height?: number
    }
  }
  jobs: MediaJob[]
  hasCompressed: boolean
}

export function VideoPicker({ onSelect, onCancel }: VideoPickerProps) {
  const [selectedVideo, setSelectedVideo] = useState<{
    videoId: string
    isCompressed: boolean
    gcsPath: string
    jobId: string
    compressedResolution?: string
    duration?: number
  } | null>(null)
  const [chunkDuration, setChunkDuration] = useState<number>(30) // Default 30 seconds

  // Fetch all videos with their jobs
  const { data: allVideosWithJobs, isLoading: isLoadingVideos } = useQuery<VideoWithJobs[]>({
    queryKey: ['videos-with-jobs'],
    queryFn: mediaApi.getAllVideosWithJobs,
    refetchInterval: 5000, // Refresh every 5 seconds for active jobs
  })

  // Filter to only show videos with completed media processing jobs
  const videosWithJobs = allVideosWithJobs?.filter(video =>
    video.jobs.some(job => job.status === MediaJobStatus.COMPLETED && job.results?.compressed_video_path)
  )

  const isEmpty = !isLoadingVideos && (!videosWithJobs || videosWithJobs.length === 0)

  if (isLoadingVideos) {
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

  if (isEmpty) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Video className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-semibold">No processed videos available</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              You need to upload and process videos in the Media workflow first
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Scene analysis requires compressed videos from media processing jobs
            </p>
            <Link href="/media">
              <Button className="mt-4">
                <ExternalLink className="mr-2 h-4 w-4" />
                Go to Media Processing
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Pick a Video</h3>
          <p className="text-sm text-muted-foreground">
            Select a video from your processed library
          </p>
        </div>
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {videosWithJobs?.map((video) => (
          <Card key={video.video_id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="line-clamp-1 text-base">{video.filename}</CardTitle>
              <CardDescription className="flex items-center gap-2">
                {video.size_bytes && formatBytes(video.size_bytes)}
                {video.metadata?.duration && (
                  <>
                    <span>•</span>
                    {formatDuration(video.metadata.duration)}
                  </>
                )}
                {video.metadata?.video?.width && video.metadata?.video?.height && (
                  <>
                    <span>•</span>
                    {video.metadata.video.width}×{video.metadata.video.height}
                  </>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {/* Processed Video Options - Only show completed jobs with compressed video */}
              {video.jobs
                .filter((job) => job.status === MediaJobStatus.COMPLETED && job.results?.compressed_video_path)
                .map((job) => (
                  <Button
                    key={job.job_id}
                    variant={
                      selectedVideo?.jobId === job.job_id
                        ? 'default'
                        : 'outline'
                    }
                    className="w-full justify-start"
                    onClick={() => {
                      if (job.results?.compressed_video_path) {
                        setSelectedVideo({
                          videoId: video.video_id,
                          isCompressed: true,
                          gcsPath: job.results.compressed_video_path,
                          jobId: job.job_id,
                          compressedResolution: job.config.compress_resolution,
                          duration: job.results.metadata?.duration,
                        })
                      }
                    }}
                  >
                    <FileVideo className="mr-2 h-4 w-4" />
                    <span className="flex-1 text-left">
                      {job.config.compress_resolution} Compressed
                      {job.results?.compression_ratio && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          ({job.results.compression_ratio.toFixed(1)}% smaller)
                        </span>
                      )}
                    </span>
                    {selectedVideo?.jobId === job.job_id && (
                      <CheckCircle className="h-4 w-4" />
                    )}
                  </Button>
                ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedVideo && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Configure Scene Analysis</CardTitle>
            <CardDescription>Set chunk duration for video processing</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Chunk Duration (seconds)
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={chunkDuration}
                  onChange={(e) => setChunkDuration(parseInt(e.target.value) || 0)}
                  className="flex h-10 w-24 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                />
                <div className="flex-1 space-y-1">
                  <p className="text-sm text-muted-foreground">
                    {chunkDuration === 0
                      ? 'No chunking - analyze entire video as one piece'
                      : `Split video into ${chunkDuration}-second chunks for analysis`
                    }
                  </p>
                  {selectedVideo.duration && chunkDuration > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Estimated {Math.ceil(selectedVideo.duration / chunkDuration)} chunks
                    </p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setChunkDuration(0)}
                >
                  No chunks
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setChunkDuration(15)}
                >
                  15s
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setChunkDuration(30)}
                >
                  30s
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setChunkDuration(60)}
                >
                  60s
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setChunkDuration(120)}
                >
                  120s
                </Button>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t pt-4">
              <Button variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  onSelect(selectedVideo.videoId, selectedVideo.isCompressed, selectedVideo.gcsPath, chunkDuration)
                }
              >
                Start Scene Analysis
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
