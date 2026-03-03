import { Upload, FileVideo, Music, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatBytes, formatDuration } from '@/lib/utils'
import { MediaJobStatus } from '@/lib/types'
import type { VideoWithJobs, SelectedVideoState } from '@/components/video-picker'

interface VideoCardProps {
  video: VideoWithJobs
  selectedVideo: SelectedVideoState | null
  onSelectVideo: (state: SelectedVideoState) => void
}

export function VideoCard({ video, selectedVideo, onSelectVideo }: VideoCardProps) {
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
        <Button
          variant={
            selectedVideo?.videoId === video.video_id && selectedVideo?.jobId === ''
              ? 'default'
              : 'outline'
          }
          className="w-full justify-start"
          onClick={() => {
            onSelectVideo({
              videoId: video.video_id,
              isCompressed: false,
              gcsPath: video.gcs_path,
              jobId: '',
              mediaType: 'video',
              duration: video.metadata?.duration,
            })
          }}
        >
          <Upload className="mr-2 h-4 w-4" />
          <span className="flex-1 text-left">
            Original Upload
            {video.size_bytes && (
              <span className="ml-1 text-xs text-muted-foreground">
                ({formatBytes(video.size_bytes)})
              </span>
            )}
            {video.metadata?.duration && (
              <span className="ml-1 text-xs text-muted-foreground">
                • {formatDuration(video.metadata.duration)}
              </span>
            )}
          </span>
          {selectedVideo?.videoId === video.video_id && selectedVideo?.jobId === '' && (
            <CheckCircle className="h-4 w-4" />
          )}
        </Button>

        {/* Processed Video and Audio Options */}
        {video.jobs
          .filter((job) =>
            job.status === MediaJobStatus.COMPLETED &&
            (job.results?.compressed_video_path || job.results?.audio_path)
          )
          .map((job) => (
            <div key={job.job_id} className="space-y-2">
              {job.results?.compressed_video_path && (
                <Button
                  variant={
                    selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'video'
                      ? 'default'
                      : 'outline'
                  }
                  className="w-full justify-start"
                  onClick={() => {
                    onSelectVideo({
                      videoId: video.video_id,
                      isCompressed: true,
                      gcsPath: job.results!.compressed_video_path!,
                      jobId: job.job_id,
                      mediaType: 'video',
                      compressedResolution: job.config.compress_resolution,
                      duration: job.results?.metadata?.duration || video.metadata?.duration,
                    })
                  }}
                >
                  <FileVideo className="mr-2 h-4 w-4" />
                  <span className="flex-1 text-left">
                    {job.config.compress_resolution} Video
                    {job.results?.compression_ratio && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({job.results.compression_ratio.toFixed(1)}% smaller)
                      </span>
                    )}
                  </span>
                  {selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'video' && (
                    <CheckCircle className="h-4 w-4" />
                  )}
                </Button>
              )}

              {job.results?.audio_path && (
                <Button
                  variant={
                    selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'audio'
                      ? 'default'
                      : 'outline'
                  }
                  className="w-full justify-start"
                  onClick={() => {
                    onSelectVideo({
                      videoId: video.video_id,
                      isCompressed: false,
                      gcsPath: job.results!.audio_path!,
                      jobId: job.job_id,
                      mediaType: 'audio',
                      audioFormat: job.config.audio_format,
                      duration: job.results?.metadata?.duration || video.metadata?.duration,
                    })
                  }}
                >
                  <Music className="mr-2 h-4 w-4" />
                  <span className="flex-1 text-left">
                    {job.config.audio_format?.toUpperCase() || 'Audio'} @ {job.config.audio_bitrate}
                    {job.results?.audio_size_bytes && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({formatBytes(job.results.audio_size_bytes)})
                      </span>
                    )}
                    {(job.results?.metadata?.duration || video.metadata?.duration) && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        • {formatDuration(job.results?.metadata?.duration || video.metadata?.duration)}
                      </span>
                    )}
                  </span>
                  {selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'audio' && (
                    <CheckCircle className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>
          ))}
      </CardContent>
    </Card>
  )
}
