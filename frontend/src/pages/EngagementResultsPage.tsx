import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { engagementApi } from '@/lib/api-client'
import { EngagementJob, EngagementJobStatus } from '@/lib/types'
import { EngagementChart } from '@/components/engagement/engagement-chart'
import { EngagementCard } from '@/components/engagement/engagement-card'

export default function EngagementResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()

  const { data: job, isLoading } = useQuery<EngagementJob>({
    queryKey: ['engagement-job', jobId],
    queryFn: () => engagementApi.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === EngagementJobStatus.PENDING || status === EngagementJobStatus.PROCESSING
        ? 3000
        : false
    },
  })

  const { data: timeseries } = useQuery({
    queryKey: ['engagement-timeseries', jobId],
    queryFn: () => engagementApi.getTimeseries(jobId!),
    enabled: !!jobId && job?.status === EngagementJobStatus.COMPLETED,
  })

  if (isLoading || !job) {
    return (
      <div className="container mx-auto max-w-6xl px-4 py-8">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading…
        </div>
      </div>
    )
  }

  const peaks = job.results?.peaks || []
  const valleys = job.results?.valleys || []
  const tokenUsage = job.results?.token_usage as { estimated_cost_usd?: number; total_tokens?: number } | undefined

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/engagement">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to engagement
          </Link>
        </Button>
        <h1 className="text-3xl font-bold font-heading">Engagement Results</h1>
        <p className="mt-1 text-muted-foreground">
          Job {job.job_id.slice(0, 8)} · video {job.video_id.slice(0, 8)} ·
          source scene job {job.source_scene_job_id.slice(0, 8)}
        </p>
      </div>

      {job.status !== EngagementJobStatus.COMPLETED ? (
        <Card>
          <CardHeader>
            <CardTitle>{job.status === EngagementJobStatus.FAILED ? 'Job failed' : 'Working…'}</CardTitle>
            <CardDescription>
              {job.status === EngagementJobStatus.FAILED
                ? job.error_message || 'See logs for details'
                : 'Status will refresh automatically.'}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="space-y-8">
          {/* Stats row */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>BARC points</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {job.results?.point_count ?? '—'}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Coverage</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {job.results?.duration_sec
                    ? `${Math.round(job.results.duration_sec)}s`
                    : '—'}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Tokens</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {tokenUsage?.total_tokens?.toLocaleString() || '—'}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Est. cost</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {tokenUsage?.estimated_cost_usd !== undefined
                    ? `$${tokenUsage.estimated_cost_usd.toFixed(4)}`
                    : '—'}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Engagement timeline</CardTitle>
              <CardDescription>
                BARC {job.results?.barc_score_column || 'engagement'} over time. Green dots = peaks, red dots = valleys.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EngagementChart
                points={timeseries?.points || []}
                peaks={peaks}
                valleys={valleys}
                scoreLabel={job.results?.barc_score_column || 'Engagement'}
              />
            </CardContent>
          </Card>

          {/* Peaks + Valleys side by side */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">Peaks</h2>
              {peaks.length === 0 ? (
                <p className="text-sm text-muted-foreground">No peaks detected.</p>
              ) : (
                peaks.map((p) => (
                  <EngagementCard key={`peak-${p.rank}`} item={p} kind="peak" />
                ))
              )}
            </div>
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">Valleys</h2>
              {valleys.length === 0 ? (
                <p className="text-sm text-muted-foreground">No valleys detected.</p>
              ) : (
                valleys.map((v) => (
                  <EngagementCard key={`valley-${v.rank}`} item={v} kind="valley" />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
