import { Coins } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface SceneJobInfoCardProps {
  sceneJob: {
    job_id: string
    status: string
    config: { compressed_video_path?: string }
    results?: Record<string, any>
    error_message?: string
  }
  totalCost: number
  totalInputCost: number
  totalOutputCost: number
  totalTokens: number
}

export function SceneJobInfoCard({
  sceneJob,
  totalCost,
  totalInputCost,
  totalOutputCost,
  totalTokens,
}: SceneJobInfoCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Scene Analysis Job</CardTitle>
        <CardDescription>Configuration and status for this analysis</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Job ID</dt>
            <dd className="mt-1 text-sm font-mono">{sceneJob.job_id}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Status</dt>
            <dd className="mt-1 text-sm capitalize">{sceneJob.status}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Est. Cost</dt>
            <dd className={`mt-1 text-sm font-medium flex flex-wrap items-center gap-1 ${totalCost > 0 ? 'text-green-600' : 'text-muted-foreground'}`}>
              {totalCost > 0 ? (
                <>
                  <div className="flex items-center gap-1">
                    <Coins className="h-3.5 w-3.5" />
                    <span className="font-mono">${totalCost.toFixed(4)}</span>
                  </div>
                  {(totalInputCost > 0 || totalOutputCost > 0) && (
                    <span className="text-xs font-normal text-muted-foreground ml-1 font-mono">
                      (In: ${totalInputCost.toFixed(4)} | Out: ${totalOutputCost.toFixed(4)})
                    </span>
                  )}
                </>
              ) : (
                <span className="text-muted-foreground font-normal">N/A (Historical)</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Total Tokens</dt>
            <dd className="mt-1 text-sm">
              {totalTokens > 0 ? <span className="font-mono">{totalTokens.toLocaleString()}</span> : <span className="text-muted-foreground">N/A</span>}
            </dd>
          </div>
          {sceneJob.config.compressed_video_path && (
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Source</dt>
              <dd className="mt-1 text-sm">Compressed video from media workflow</dd>
            </div>
          )}
          {sceneJob.error_message && (
            <div className="col-span-full">
              <dt className="text-sm font-medium text-destructive">Error</dt>
              <dd className="mt-1 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                {sceneJob.error_message}
              </dd>
            </div>
          )}
        </dl>
      </CardContent>
    </Card>
  )
}
