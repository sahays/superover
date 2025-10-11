'use client'

import { SceneJob, SceneJobStatus } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CheckCircle, XCircle, Loader2, Eye, Trash2 } from 'lucide-react'
import Link from 'next/link'

interface SceneJobCardProps {
  job: SceneJob
  videoFilename?: string
  onDelete?: (jobId: string) => void
}

export function SceneJobCard({ job, videoFilename, onDelete }: SceneJobCardProps) {
  const getStatusBadge = (status: SceneJobStatus) => {
    switch (status) {
      case SceneJobStatus.COMPLETED:
        return (
          <Badge variant="default" className="bg-green-600">
            <CheckCircle className="mr-1 h-3 w-3" />
            Completed
          </Badge>
        )
      case SceneJobStatus.PROCESSING:
        // Show the actual processing step if available
        const stepLabel = job.results?.step
          ? job.results.step.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
          : 'Processing'
        return (
          <Badge variant="default" className="bg-blue-600">
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            {stepLabel}
          </Badge>
        )
      case SceneJobStatus.FAILED:
        return (
          <Badge variant="destructive">
            <XCircle className="mr-1 h-3 w-3" />
            Failed
          </Badge>
        )
      case SceneJobStatus.PENDING:
        return <Badge variant="outline">Pending</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getProgressInfo = () => {
    if (job.status === SceneJobStatus.PROCESSING && job.results?.progress) {
      const { completed_chunks, total_chunks } = job.results.progress
      if (total_chunks > 0) {
        const percentage = Math.round((completed_chunks / total_chunks) * 100)
        return (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Analyzing chunks</span>
              <span>{completed_chunks} / {total_chunks}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>
        )
      }
    }
    return null
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base">Scene Analysis Job</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {videoFilename || 'Unknown video'}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {new Date(job.created_at || '').toLocaleString()}
            </p>
          </div>
          {getStatusBadge(job.status)}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Configuration */}
        <div className="grid gap-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Chunk Duration:</span>
            <span className="font-medium">
              {job.config.chunk_duration > 0
                ? `${job.config.chunk_duration}s`
                : 'No chunking'}
            </span>
          </div>
          {job.config.compressed_video_path && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Source:</span>
              <span className="font-medium text-xs">Compressed video</span>
            </div>
          )}
        </div>

        {/* Progress */}
        {job.status === SceneJobStatus.PROCESSING && getProgressInfo()}

        {/* Results */}
        {job.status === SceneJobStatus.COMPLETED && job.results && (
          <div className="space-y-2 rounded-lg bg-gray-50 p-3 text-sm">
            {job.results.chunks_analyzed !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Chunks Analyzed:</span>
                <span className="font-medium">{job.results.chunks_analyzed}</span>
              </div>
            )}
            {job.results.manifest_created && (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="h-4 w-4" />
                <span>Manifest created</span>
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {job.status === SceneJobStatus.FAILED && job.error_message && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-900">
            {job.error_message}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {job.status === SceneJobStatus.COMPLETED && (
            <Button asChild variant="outline" size="sm" className="flex-1">
              <Link href={`/scene/${job.job_id}`}>
                <Eye className="mr-2 h-4 w-4" />
                View Results
              </Link>
            </Button>
          )}
          {job.status !== SceneJobStatus.COMPLETED && onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const message = job.status === SceneJobStatus.PROCESSING
                  ? 'This job appears to be stuck. Delete it? The original video will not be deleted.'
                  : 'Delete this scene job and all analysis results? The original video will not be deleted.'
                if (confirm(message)) {
                  onDelete(job.job_id)
                }
              }}
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
