import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatBytes, formatDuration } from '@/lib/utils'

interface SceneVideoMetadataCardProps {
  scene: {
    video_id: string
    filename: string
    status: string
    size_bytes?: number
    content_type?: string
    metadata?: {
      duration?: number
      video?: { width?: number; height?: number }
    }
    error_message?: string
  }
}

export function SceneVideoMetadataCard({ scene }: SceneVideoMetadataCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">{scene.filename}</CardTitle>
        <CardDescription>
          Status: {scene.status}
          {scene.size_bytes && ` • ${formatBytes(scene.size_bytes)}`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Scene ID</dt>
            <dd className="mt-1 text-sm font-mono">{scene.video_id}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Content Type</dt>
            <dd className="mt-1 text-sm">{scene.content_type || 'N/A'}</dd>
          </div>
          {scene.metadata?.duration && (
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Duration</dt>
              <dd className="mt-1 text-sm">{formatDuration(scene.metadata.duration)}</dd>
            </div>
          )}
          {scene.metadata?.video && (
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Resolution</dt>
              <dd className="mt-1 text-sm">
                {scene.metadata.video.width} x {scene.metadata.video.height}
              </dd>
            </div>
          )}
          {scene.error_message && (
            <div className="col-span-full">
              <dt className="text-sm font-medium text-destructive">Error</dt>
              <dd className="mt-1 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                {scene.error_message}
              </dd>
            </div>
          )}
        </dl>
      </CardContent>
    </Card>
  )
}
