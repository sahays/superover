import { useMemo, useState } from 'react'
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
import { EntityFilter } from '@/components/engagement/entity-filter'
import { DialogDrawer } from '@/components/engagement/dialog-drawer'
import {
  RecommendationsPanel,
  type RecommendationsPayload,
} from '@/components/engagement/recommendations-panel'

export default function EngagementResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [activeTimestamp, setActiveTimestamp] = useState<number | null>(null)
  const [selectedEntities, setSelectedEntities] = useState<Set<string>>(new Set())

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

  const isCompleted = job?.status === EngagementJobStatus.COMPLETED

  const { data: timeseries } = useQuery({
    queryKey: ['engagement-timeseries', jobId],
    queryFn: () => engagementApi.getTimeseries(jobId!),
    enabled: !!jobId && isCompleted,
  })

  const { data: entities } = useQuery({
    queryKey: ['engagement-entities', jobId],
    queryFn: () => engagementApi.getEntities(jobId!),
    enabled: !!jobId && isCompleted,
    staleTime: 60_000,
  })

  const { data: recommendations } = useQuery<RecommendationsPayload>({
    queryKey: ['engagement-recommendations', jobId],
    queryFn: () => engagementApi.getRecommendations(jobId!) as Promise<RecommendationsPayload>,
    enabled: !!jobId && isCompleted,
    staleTime: 60_000,
  })

  // Selected entity ranges → highlight bands on the chart
  const highlightRanges = useMemo(() => {
    if (!entities || selectedEntities.size === 0) return []
    return entities
      .filter((e) => selectedEntities.has(e.name))
      .flatMap((e) =>
        e.appearances.map((r) => ({ start: r.start_sec, end: r.end_sec, label: e.name }))
      )
  }, [entities, selectedEntities])

  // Avg engagement during selected ranges
  const { overallAvg, selectionAvg } = useMemo(() => {
    const primary = timeseries?.primary_metric
    const points: [number, number][] = primary && timeseries?.metrics
      ? (timeseries.metrics[primary] as [number, number][]) || []
      : timeseries?.points || []
    if (points.length === 0) return { overallAvg: undefined, selectionAvg: undefined }
    const allScores = points.map(([, s]) => s)
    const overall = allScores.reduce((a, b) => a + b, 0) / allScores.length
    if (highlightRanges.length === 0) return { overallAvg: overall, selectionAvg: undefined }
    const inRange = points.filter(([t]) =>
      highlightRanges.some((r) => t >= r.start && t <= r.end)
    )
    const sel = inRange.length > 0
      ? inRange.reduce((a, [, s]) => a + s, 0) / inRange.length
      : undefined
    return { overallAvg: overall, selectionAvg: sel }
  }, [timeseries, highlightRanges])

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

  const toggleEntity = (name: string) =>
    setSelectedEntities((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })

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

      {!isCompleted ? (
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
          {/* Recommendations — top of the page so producers see prescriptive guidance first */}
          {recommendations && (
            <RecommendationsPanel
              data={recommendations}
              onAnchorClick={(t) => setActiveTimestamp(t)}
            />
          )}

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

          {/* Entity / event chips */}
          {entities && entities.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Filter by character or event</CardTitle>
                <CardDescription>
                  Click a chip to highlight where that entity appears and compare its
                  average engagement to the overall.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EntityFilter
                  entities={entities}
                  selected={selectedEntities}
                  onToggle={toggleEntity}
                  overallAvg={overallAvg}
                  selectionAvg={selectionAvg}
                />
              </CardContent>
            </Card>
          )}

          {/* Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Engagement timeline</CardTitle>
              <CardDescription>
                Click any point to see the dialog at that moment. Green dots are
                peaks, red dots are valleys.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EngagementChart
                metrics={timeseries?.metrics || {}}
                primaryMetric={timeseries?.primary_metric}
                peaks={peaks}
                valleys={valleys}
                highlightRanges={highlightRanges}
                onPointSelect={(t) => setActiveTimestamp(t)}
              />
            </CardContent>
          </Card>

          {/* Peaks + Valleys */}
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

      {/* Click-a-point drawer */}
      {jobId && (
        <DialogDrawer
          jobId={jobId}
          activeTimestamp={activeTimestamp}
          onClose={() => setActiveTimestamp(null)}
        />
      )}
    </div>
  )
}
