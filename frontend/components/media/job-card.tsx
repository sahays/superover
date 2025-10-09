'use client'

import { MediaJob, MediaJobStatus } from '@/lib/types'
import { formatBytes } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CheckCircle, XCircle, Loader2, Download, Trash2 } from 'lucide-react'
import Link from 'next/link'

interface JobCardProps {
  job: MediaJob
  onDelete?: (jobId: string) => void
}

export function JobCard({ job, onDelete }: JobCardProps) {
  const getStatusBadge = (status: MediaJobStatus) => {
    switch (status) {
      case MediaJobStatus.COMPLETED:
        return (
          <Badge variant="default" className="bg-green-600">
            <CheckCircle className="mr-1 h-3 w-3" />
            Completed
          </Badge>
        )
      case MediaJobStatus.PROCESSING:
        // Show the actual processing step if available
        const stepLabel = job.progress?.step
          ? job.progress.step.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
          : 'Processing'
        return (
          <Badge variant="default" className="bg-blue-600">
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            {stepLabel}
          </Badge>
        )
      case MediaJobStatus.FAILED:
        return (
          <Badge variant="destructive">
            <XCircle className="mr-1 h-3 w-3" />
            Failed
          </Badge>
        )
      case MediaJobStatus.PENDING:
        return <Badge variant="outline">Pending</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getProgressStep = () => {
    if (job.progress) {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="capitalize">{job.progress.step?.replace('_', ' ')}</span>
            <span>{job.progress.percent}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${job.progress.percent}%` }}
            />
          </div>
        </div>
      )
    }
    return null
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base">Media Processing Job</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {new Date(job.created_at || '').toLocaleString()}
            </p>
          </div>
          {getStatusBadge(job.status)}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Configuration */}
        <div className="grid gap-2 text-sm">
          {job.config.compress && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Compression:</span>
              <span className="font-medium">{job.config.compress_resolution}</span>
            </div>
          )}
          {job.config.extract_audio && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Audio:</span>
              <span className="font-medium">
                {job.config.audio_format?.toUpperCase()} @ {job.config.audio_bitrate}
              </span>
            </div>
          )}
        </div>

        {/* Progress */}
        {job.status === MediaJobStatus.PROCESSING && getProgressStep()}

        {/* Results */}
        {job.status === MediaJobStatus.COMPLETED && job.results && (
          <div className="space-y-2 rounded-lg bg-gray-50 p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Original Size:</span>
              <span className="font-medium">
                {formatBytes(job.results.original_size_bytes)}
              </span>
            </div>
            {job.results.compressed_video_path && (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Compressed Size:</span>
                  <span className="font-medium">
                    {formatBytes(job.results.compressed_size_bytes)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Reduction:</span>
                  <span className="font-medium text-green-600">
                    {job.results.compression_ratio.toFixed(1)}%
                  </span>
                </div>
              </>
            )}
            {job.results.audio_path && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Audio Size:</span>
                <span className="font-medium">
                  {formatBytes(job.results.audio_size_bytes)}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {job.status === MediaJobStatus.FAILED && job.error_message && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-900">
            {job.error_message}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {job.status === MediaJobStatus.COMPLETED && (
            <Button asChild variant="outline" size="sm" className="flex-1">
              <Link href={`/media/${job.job_id}`}>
                View Details
              </Link>
            </Button>
          )}
          {job.status !== MediaJobStatus.PROCESSING && onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm('Delete this job and all generated files? The original video will not be deleted.')) {
                  onDelete(job.job_id)
                }
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
