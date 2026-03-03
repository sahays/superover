import { Upload, FileVideo, Music } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { formatBytes, formatDuration } from '@/lib/utils'
import { MediaJobStatus } from '@/lib/types'
import type { VideoWithJobs, SelectedVideoState } from '@/components/video-picker'

interface VideoCardProps {
  video: VideoWithJobs
  selectedVideos: Map<string, SelectedVideoState>
  onToggleVideo: (key: string, state: SelectedVideoState) => void
}

export function VideoCard({ video, selectedVideos, onToggleVideo }: VideoCardProps) {
  // Build a unique key for each media option
  const originalKey = `${video.video_id}::original`

  return (
    <Card className="overflow-hidden">
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
        {/* Original Upload Option */}
        <label
          className={`flex items-center gap-3 rounded-md border p-3 cursor-pointer transition-colors ${
            selectedVideos.has(originalKey) ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
          }`}
        >
          <Checkbox
            checked={selectedVideos.has(originalKey)}
            onCheckedChange={() =>
              onToggleVideo(originalKey, {
                videoId: video.video_id,
                isCompressed: false,
                gcsPath: video.gcs_path,
                jobId: '',
                mediaType: 'video',
                duration: video.metadata?.duration,
              })
            }
          />
          <Upload className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="flex-1 text-sm">
            Original Upload
            {video.size_bytes && (
              <span className="ml-1 text-xs text-muted-foreground">
                ({formatBytes(video.size_bytes)})
              </span>
            )}
          </span>
        </label>

        {/* Processed Video and Audio Options */}
        {video.jobs
          .filter((job) =>
            job.status === MediaJobStatus.COMPLETED &&
            (job.results?.compressed_video_path || job.results?.audio_path)
          )
          .map((job) => {
            const videoKey = `${video.video_id}::video::${job.job_id}`
            const audioKey = `${video.video_id}::audio::${job.job_id}`

            return (
              <div key={job.job_id} className="space-y-2">
                {job.results?.compressed_video_path && (
                  <label
                    className={`flex items-center gap-3 rounded-md border p-3 cursor-pointer transition-colors ${
                      selectedVideos.has(videoKey) ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    }`}
                  >
                    <Checkbox
                      checked={selectedVideos.has(videoKey)}
                      onCheckedChange={() =>
                        onToggleVideo(videoKey, {
                          videoId: video.video_id,
                          isCompressed: true,
                          gcsPath: job.results!.compressed_video_path!,
                          jobId: job.job_id,
                          mediaType: 'video',
                          compressedResolution: job.config.compress_resolution,
                          duration: job.results?.metadata?.duration || video.metadata?.duration,
                        })
                      }
                    />
                    <FileVideo className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="flex-1 text-sm">
                      {job.config.compress_resolution} Video
                      {job.results?.compression_ratio && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          ({job.results.compression_ratio.toFixed(1)}% smaller)
                        </span>
                      )}
                    </span>
                  </label>
                )}

                {job.results?.audio_path && (
                  <label
                    className={`flex items-center gap-3 rounded-md border p-3 cursor-pointer transition-colors ${
                      selectedVideos.has(audioKey) ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    }`}
                  >
                    <Checkbox
                      checked={selectedVideos.has(audioKey)}
                      onCheckedChange={() =>
                        onToggleVideo(audioKey, {
                          videoId: video.video_id,
                          isCompressed: false,
                          gcsPath: job.results!.audio_path!,
                          jobId: job.job_id,
                          mediaType: 'audio',
                          audioFormat: job.config.audio_format,
                          duration: job.results?.metadata?.duration || video.metadata?.duration,
                        })
                      }
                    />
                    <Music className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="flex-1 text-sm">
                      {job.config.audio_format?.toUpperCase() || 'Audio'} @ {job.config.audio_bitrate}
                      {job.results?.audio_size_bytes && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          ({formatBytes(job.results.audio_size_bytes)})
                        </span>
                      )}
                    </span>
                  </label>
                )}
              </div>
            )
          })}
      </CardContent>
    </Card>
  )
}
