import { useCallback, useMemo, useRef, useState } from 'react'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { engagementApi, videoApi } from '@/lib/api-client'
import { EngagementJob, EngagementJobStatus, Video } from '@/lib/types'
import { formatDuration } from '@/lib/utils'
import { computeEntityDeltas } from '@/lib/engagement-influence'
import { activeEntityNames, entityColor } from '@/lib/engagement-moment'
import { EngagementChart } from '@/components/engagement/engagement-chart'
import { EngagementCard } from '@/components/engagement/engagement-card'
import { EntityFilter } from '@/components/engagement/entity-filter'
import { DialogDrawer } from '@/components/engagement/dialog-drawer'
import { InfluenceRanking } from '@/components/engagement/influence-ranking'
import { MomentPanel } from '@/components/engagement/moment-panel'
import {
  EngagementVideoPlayer,
  type EngagementVideoPlayerHandle,
} from '@/components/engagement/engagement-video-player'
import {
  RecommendationsPanel,
  type RecommendationsPayload,
} from '@/components/engagement/recommendations-panel'

// 75th-percentile target, mirroring the backend's compute_stats default.
function quantile(values: number[], q: number): number | undefined {
  if (values.length === 0) return undefined
  const s = [...values].sort((a, b) => a - b)
  const idx = (s.length - 1) * q
  const lo = Math.floor(idx)
  const hi = Math.min(lo + 1, s.length - 1)
  return s[lo] * (1 - (idx - lo)) + s[hi] * (idx - lo)
}

export default function EngagementResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [activeTimestamp, setActiveTimestamp] = useState<number | null>(null)
  const [drawerAt, setDrawerAt] = useState<number | null>(null)
  const [selectedEntities, setSelectedEntities] = useState<Set<string>>(new Set())
  const playerRef = useRef<EngagementVideoPlayerHandle>(null)
  const lastTickRef = useRef(0)

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

  // Video fetched as soon as we know the id (even while processing) so the
  // page title can show the filename.
  const { data: video } = useQuery<Video>({
    queryKey: ['engagement-video', job?.video_id],
    queryFn: () => videoApi.getVideo(job!.video_id) as Promise<Video>,
    enabled: !!job?.video_id,
    staleTime: 60_000,
  })

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

  const { data: scenes } = useQuery({
    queryKey: ['engagement-scenes', jobId],
    queryFn: () => engagementApi.getScenes(jobId!).catch(() => []),
    enabled: !!jobId && isCompleted,
    staleTime: 60_000,
  })

  const { data: markers } = useQuery({
    queryKey: ['engagement-markers', jobId],
    queryFn: () => engagementApi.getMarkers(jobId!).catch(() => []),
    enabled: !!jobId && isCompleted,
    staleTime: 60_000,
  })

  const { data: cues } = useQuery({
    queryKey: ['engagement-cues', jobId],
    queryFn: () => engagementApi.getCues(jobId!),
    enabled: !!jobId && isCompleted,
    staleTime: 60_000,
  })

  const { data: recommendations } = useQuery<RecommendationsPayload>({
    queryKey: ['engagement-recommendations', jobId],
    queryFn: () => engagementApi.getRecommendations(jobId!) as Promise<RecommendationsPayload>,
    enabled: !!jobId && isCompleted,
    staleTime: 60_000,
  })

  const primaryPoints = useMemo<[number, number][]>(() => {
    const primary = timeseries?.primary_metric
    return primary && timeseries?.metrics
      ? (timeseries.metrics[primary] as [number, number][]) || []
      : timeseries?.points || []
  }, [timeseries])

  const { overallAvg, targetAvg } = useMemo(() => {
    const scores = primaryPoints.map(([, s]) => s)
    if (scores.length === 0) return { overallAvg: undefined, targetAvg: undefined }
    return {
      overallAvg: scores.reduce((a, b) => a + b, 0) / scores.length,
      targetAvg: quantile(scores, 0.75),
    }
  }, [primaryPoints])

  const highlightRanges = useMemo(() => {
    if (!entities || selectedEntities.size === 0) return []
    return entities
      .filter((e) => selectedEntities.has(e.name))
      .flatMap((e) =>
        e.appearances.map((r) => ({
          start: r.start_sec,
          end: r.end_sec,
          label: e.name,
          color: entityColor(e.name, e.kind),
        }))
      )
  }, [entities, selectedEntities])

  const selectionAvg = useMemo(() => {
    if (primaryPoints.length === 0 || highlightRanges.length === 0) return undefined
    const inRange = primaryPoints.filter(([t]) => highlightRanges.some((r) => t >= r.start && t <= r.end))
    return inRange.length > 0 ? inRange.reduce((a, [, s]) => a + s, 0) / inRange.length : undefined
  }, [primaryPoints, highlightRanges])

  const emotionBands = useMemo(() => {
    if (!entities) return []
    return entities
      .filter((e) => e.kind === 'emotion')
      .flatMap((e) =>
        e.appearances.map((r) => ({
          start_sec: r.start_sec,
          end_sec: r.end_sec,
          label: e.name,
          intensity: e.avg_intensity ?? undefined,
        }))
      )
  }, [entities])

  const { characterDeltas, emotionDeltas } = useMemo(() => {
    const deltas = computeEntityDeltas(entities, primaryPoints)
    return {
      characterDeltas: deltas.filter((d) => d.kind === 'character'),
      emotionDeltas: deltas.filter((d) => d.kind === 'emotion'),
    }
  }, [entities, primaryPoints])

  const activeNames = useMemo(
    () => (activeTimestamp == null ? new Set<string>() : activeEntityNames(entities, activeTimestamp)),
    [entities, activeTimestamp]
  )

  // Exclusive selection: one entity at a time. Clicking a new chip replaces the
  // current selection; clicking the active chip clears it.
  const toggleEntity = useCallback(
    (name: string) =>
      setSelectedEntities((prev) => (prev.has(name) && prev.size === 1 ? new Set() : new Set([name]))),
    []
  )

  // Clicking anywhere moves the shared playhead and positions the video.
  const goToTimestamp = useCallback((t: number) => {
    setActiveTimestamp(t)
    playerRef.current?.seekTo(t)
  }, [])

  // Selecting a filter (entity pill / influence row) highlights it AND jumps the
  // playhead to that entity's first appearance so the spine reflects the choice.
  const selectEntity = useCallback(
    (name: string) => {
      const isOnlySelected = selectedEntities.has(name) && selectedEntities.size === 1
      if (isOnlySelected) {
        setSelectedEntities(new Set())
        return
      }
      setSelectedEntities(new Set([name]))
      const ent = entities?.find((e) => e.name === name)
      if (ent?.appearances?.length) {
        goToTimestamp(Math.min(...ent.appearances.map((a) => a.start_sec)))
      }
    },
    [selectedEntities, entities, goToTimestamp]
  )

  // Live follow: throttle the ~4Hz timeupdate to 0.5s steps.
  const onVideoTime = useCallback((sec: number) => {
    if (Math.abs(sec - lastTickRef.current) < 0.5) return
    lastTickRef.current = sec
    setActiveTimestamp(sec)
  }, [])

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
  const episodeSummary = job.results?.episode_summary
  const tokenUsage = job.results?.token_usage as
    | { estimated_cost_usd?: number; total_tokens?: number }
    | undefined

  const isActiveExtremum = (ts: number) => activeTimestamp != null && Math.abs(ts - activeTimestamp) <= 8

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/engagement">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to engagement
          </Link>
        </Button>
        <h1 className="text-3xl font-bold font-heading">
          {video?.filename || 'Engagement analysis'}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {job.status}
          {video?.metadata?.duration ? ` · ${formatDuration(Number(video.metadata.duration))}` : ''}
          {' · '}job {job.job_id.slice(0, 8)} · source {job.source_scene_job_id.slice(0, 8)}
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
        <div className="space-y-6">
          {/* ── Spine: video + "At this moment" + timeline (always at top) ── */}
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <EngagementVideoPlayer ref={playerRef} videoId={job.video_id} onTime={onVideoTime} />
            </div>
            <MomentPanel
              timestamp={activeTimestamp}
              points={primaryPoints}
              overallAvg={overallAvg}
              scenes={scenes || []}
              entities={entities}
              cues={cues}
              selected={selectedEntities}
              onToggleEntity={toggleEntity}
              onOpenDialog={() => setDrawerAt(activeTimestamp ?? 0)}
            />
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Engagement timeline</CardTitle>
              <CardDescription>
                Press play or click anywhere to move the playhead — the panel above and
                the tabs below follow. Hover for the scene; the ribbon shows mood &amp; key moments.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EngagementChart
                metrics={timeseries?.metrics || {}}
                primaryMetric={timeseries?.primary_metric}
                peaks={peaks}
                valleys={valleys}
                highlightRanges={highlightRanges}
                scenes={scenes || []}
                playhead={activeTimestamp}
                overallAvg={overallAvg}
                targetAvg={targetAvg}
                emotionBands={emotionBands}
                markers={markers || []}
                selectedNames={selectedEntities}
                onPointSelect={goToTimestamp}
                onBandToggle={toggleEntity}
              />
            </CardContent>
          </Card>

          {/* ── Reactive detail tabs ── */}
          <Tabs defaultValue="overview" className="w-full">
            <TabsList className="mb-2 flex-wrap">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="peaks">Peaks &amp; Valleys</TabsTrigger>
              <TabsTrigger value="characters">Characters &amp; Emotion</TabsTrigger>
              <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-6">
              <div className="grid gap-4 md:grid-cols-4">
                <StatCard label="BARC points" value={job.results?.point_count ?? '—'} />
                <StatCard
                  label="Coverage"
                  value={job.results?.duration_sec ? `${Math.round(job.results.duration_sec)}s` : '—'}
                />
                <StatCard label="Tokens" value={tokenUsage?.total_tokens?.toLocaleString() || '—'} />
                <StatCard
                  label="Est. cost"
                  value={
                    tokenUsage?.estimated_cost_usd !== undefined
                      ? `$${tokenUsage.estimated_cost_usd.toFixed(4)}`
                      : '—'
                  }
                />
              </div>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Episode summary</CardTitle>
                </CardHeader>
                <CardContent>
                  {episodeSummary ? (
                    <p className="text-sm leading-relaxed">{episodeSummary}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">No episode summary available.</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="peaks" className="space-y-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="space-y-4">
                  <h2 className="text-xl font-semibold">Peaks</h2>
                  {peaks.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No peaks detected.</p>
                  ) : (
                    peaks.map((p) => (
                      <EngagementCard
                        key={`peak-${p.rank}`}
                        item={p}
                        kind="peak"
                        isActive={isActiveExtremum(p.timestamp_sec)}
                        onSelect={goToTimestamp}
                      />
                    ))
                  )}
                </div>
                <div className="space-y-4">
                  <h2 className="text-xl font-semibold">Valleys</h2>
                  {valleys.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No valleys detected.</p>
                  ) : (
                    valleys.map((v) => (
                      <EngagementCard
                        key={`valley-${v.rank}`}
                        item={v}
                        kind="valley"
                        isActive={isActiveExtremum(v.timestamp_sec)}
                        onSelect={goToTimestamp}
                      />
                    ))
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="characters" className="space-y-6">
              {entities && entities.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Filter the timeline</CardTitle>
                    <CardDescription>
                      Click a chip to highlight where it appears on the timeline above.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <EntityFilter
                      entities={entities}
                      selected={selectedEntities}
                      onToggle={selectEntity}
                      overallAvg={overallAvg}
                      selectionAvg={selectionAvg}
                    />
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Character influence on rating</CardTitle>
                  <CardDescription>
                    Avg BARC rating while each character is on screen vs the overall average.
                    A dot marks who's on screen at the playhead.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <InfluenceRanking
                    title=""
                    items={characterDeltas}
                    selected={selectedEntities}
                    activeNames={activeNames}
                    onToggle={selectEntity}
                    emptyText="No character influence yet (needs re-analysis with character data)."
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Emotion influence on rating</CardTitle>
                  <CardDescription>
                    Avg BARC rating during each emotion vs the overall average.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <InfluenceRanking
                    title=""
                    items={emotionDeltas}
                    selected={selectedEntities}
                    activeNames={activeNames}
                    onToggle={selectEntity}
                    emptyText="No emotion data yet — re-run scene analysis to populate emotions."
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="recommendations" className="space-y-6">
              {recommendations ? (
                <RecommendationsPanel
                  data={recommendations}
                  onAnchorClick={goToTimestamp}
                  activeTimestamp={activeTimestamp}
                />
              ) : (
                <p className="text-sm text-muted-foreground">No recommendations available.</p>
              )}
            </TabsContent>
          </Tabs>
        </div>
      )}

      {/* On-demand dialog drawer (opened from the moment panel). */}
      {jobId && (
        <DialogDrawer jobId={jobId} activeTimestamp={drawerAt} onClose={() => setDrawerAt(null)} />
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="font-mono text-2xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}
