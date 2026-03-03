import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatBytes } from '@/lib/utils'

interface JobResultsCardProps {
  results: {
    original_size_bytes: number
    compressed_video_path?: string | null
    compressed_size_bytes?: number
    compression_ratio?: number
    audio_path?: string | null
    audio_size_bytes?: number
    metadata?: Record<string, unknown>
  }
}

export function JobResultsCard({ results }: JobResultsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 text-sm">
          <div className="flex justify-between">
            <dt className="font-medium text-muted-foreground">Original Size</dt>
            <dd className="font-medium">{formatBytes(results.original_size_bytes)}</dd>
          </div>
          {results.compressed_video_path && (
            <>
              <div className="flex justify-between">
                <dt className="font-medium text-muted-foreground">Compressed Size</dt>
                <dd className="font-medium">{formatBytes(results.compressed_size_bytes || 0)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="font-medium text-muted-foreground">Size Reduction</dt>
                <dd className="font-medium text-green-600 dark:text-green-400">
                  {(results.compression_ratio || 0).toFixed(1)}%
                </dd>
              </div>
              <div className="col-span-full">
                <dt className="font-medium text-muted-foreground">Compressed Video Path</dt>
                <dd className="mt-1 break-all font-mono text-xs text-blue-600 dark:text-blue-400">
                  {results.compressed_video_path}
                </dd>
              </div>
            </>
          )}
          {results.audio_path && (
            <>
              <div className="flex justify-between">
                <dt className="font-medium text-muted-foreground">Audio Size</dt>
                <dd className="font-medium">{formatBytes(results.audio_size_bytes || 0)}</dd>
              </div>
              <div className="col-span-full">
                <dt className="font-medium text-muted-foreground">Audio File Path</dt>
                <dd className="mt-1 break-all font-mono text-xs text-blue-600 dark:text-blue-400">
                  {results.audio_path}
                </dd>
              </div>
            </>
          )}
        </dl>

        {results.metadata && (
          <details className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800">
            <summary className="cursor-pointer font-medium">View Full Metadata</summary>
            <pre className="mt-3 overflow-x-auto text-xs">
              {JSON.stringify(results.metadata, null, 2)}
            </pre>
          </details>
        )}
      </CardContent>
    </Card>
  )
}
