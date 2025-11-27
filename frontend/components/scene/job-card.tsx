'use client'

import { useState } from 'react'
import { SceneJob, SceneJobStatus } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { CheckCircle, XCircle, Loader2, Eye, Trash2, FileText, Clock, Coins } from 'lucide-react'
import Link from 'next/link'
import { truncateFilename } from '@/lib/utils'

interface SceneJobCardProps {
  job: SceneJob
  videoFilename?: string
  onDelete?: (jobId: string) => void
}

export function SceneJobCard({ job, videoFilename, onDelete }: SceneJobCardProps) {
  const [showPromptDialog, setShowPromptDialog] = useState(false)

  // Get prompt type label (use 'custom' if not specified for backward compatibility)
  const getPromptTypeLabel = (type?: string) => {
    if (!type) return 'Custom'
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  // Calculate time taken for completed jobs
  const getTimeTaken = () => {
    if (job.status === SceneJobStatus.COMPLETED && job.created_at && job.updated_at) {
      const start = new Date(job.created_at).getTime()
      const end = new Date(job.updated_at).getTime()
      const diffMs = end - start
      const diffSec = Math.floor(diffMs / 1000)
      const diffMin = Math.floor(diffSec / 60)
      const diffHour = Math.floor(diffMin / 60)

      if (diffHour > 0) {
        return `${diffHour}h ${diffMin % 60}m`
      } else if (diffMin > 0) {
        return `${diffMin}m ${diffSec % 60}s`
      } else {
        return `${diffSec}s`
      }
    }
    return null
  }

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
          <div className="flex-1">
            <CardTitle className="text-base">
              {truncateFilename(job.prompt_name || 'Scene Analysis Job', 40)}
            </CardTitle>
            {videoFilename && (
              <div className="mt-1 flex items-center gap-1.5 text-sm font-medium text-foreground/80">
                <FileText className="h-3.5 w-3.5" />
                <span>{truncateFilename(videoFilename, 35)}</span>
              </div>
            )}
            {job.status === SceneJobStatus.COMPLETED && getTimeTaken() && (
              <div className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Clock className="h-3.5 w-3.5" />
                <span>{getTimeTaken()}</span>
              </div>
            )}
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
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Prompt Type:</span>
            {job.prompt_text ? (
              <Badge
                variant="outline"
                className="text-xs cursor-pointer hover:bg-muted transition-colors flex items-center gap-1"
                onClick={() => setShowPromptDialog(true)}
              >
                {getPromptTypeLabel(job.prompt_type)}
                <Eye className="h-3 w-3" />
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs">
                {getPromptTypeLabel(job.prompt_type)}
              </Badge>
            )}
          </div>
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

      {/* Prompt Dialog */}
      <Dialog open={showPromptDialog} onOpenChange={setShowPromptDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Analysis Prompt</DialogTitle>
            <DialogDescription>
              The prompt used for this scene analysis job
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto">
            <div className="rounded-lg bg-gray-50 p-4">
              <pre className="whitespace-pre-wrap text-sm font-mono">
                {job.prompt_text}
              </pre>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
