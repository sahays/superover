import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  BarChart3,
  CheckCircle,
  Clock,
  Eye,
  FileSpreadsheet,
  Loader2,
  Trash2,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { engagementApi, videoApi } from '@/lib/api-client'
import {
  EngagementJob,
  EngagementJobStatus,
  Video,
} from '@/lib/types'
import { useAuthStore } from '@/store/useAuthStore'

function StatusBadge({ status }: { status: EngagementJobStatus }) {
  switch (status) {
    case EngagementJobStatus.COMPLETED:
      return (
        <Badge className="bg-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Completed
        </Badge>
      )
    case EngagementJobStatus.PROCESSING:
      return (
        <Badge className="bg-blue-600">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Processing
        </Badge>
      )
    case EngagementJobStatus.FAILED:
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      )
    case EngagementJobStatus.PENDING:
    default:
      return (
        <Badge variant="outline">
          <Clock className="mr-1 h-3 w-3" />
          Pending
        </Badge>
      )
  }
}

function EngagementJobCard({
  job,
  videoFilename,
  onDelete,
}: {
  job: EngagementJob
  videoFilename?: string
  onDelete?: (jobId: string) => void
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base truncate">
              {videoFilename || job.video_id}
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {job.created_at ? new Date(job.created_at).toLocaleString() : '—'}
            </p>
          </div>
          <StatusBadge status={job.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm text-muted-foreground">
          <div className="flex justify-between">
            <span>Source scene job:</span>
            <span className="font-mono text-xs">{job.source_scene_job_id.slice(0, 8)}</span>
          </div>
          {job.results?.point_count !== undefined && job.results?.point_count !== null && (
            <div className="flex justify-between">
              <span>BARC points:</span>
              <span className="font-mono text-xs">{job.results.point_count}</span>
            </div>
          )}
        </div>

        {job.status === EngagementJobStatus.FAILED && job.error_message && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-900">
            {job.error_message}
          </div>
        )}

        <div className="flex gap-2">
          {job.status === EngagementJobStatus.COMPLETED && (
            <Button asChild variant="outline" size="sm" className="flex-1">
              <Link to={`/engagement/${job.job_id}`}>
                <Eye className="mr-2 h-4 w-4" />
                View Results
              </Link>
            </Button>
          )}
          {onDelete && job.status !== EngagementJobStatus.PROCESSING && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm('Delete this engagement analysis?')) onDelete(job.job_id)
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

export default function EngagementAnalysisPage() {
  const { isMaster } = useAuthStore()
  const [filterVideoId, setFilterVideoId] = useState<string>('all')
  const [videoFilenames, setVideoFilenames] = useState<Record<string, string>>({})

  const { data: videos } = useQuery({
    queryKey: ['videos-list-engagement'],
    queryFn: () => videoApi.listVideos(50) as Promise<Video[]>,
  })

  // /api/scenes lists per-job (one row per scene job), so the same video can
  // appear many times. Dedupe by video_id for our dropdown + fan-out.
  const uniqueVideos = useMemo(() => {
    const seen = new Set<string>()
    const out: Video[] = []
    for (const v of videos || []) {
      if (!seen.has(v.video_id)) {
        seen.add(v.video_id)
        out.push(v)
      }
    }
    return out
  }, [videos])

  useEffect(() => {
    if (!uniqueVideos.length) return
    const map: Record<string, string> = {}
    for (const v of uniqueVideos) map[v.video_id] = v.filename
    setVideoFilenames((prev) => ({ ...prev, ...map }))
  }, [uniqueVideos])

  const { data: jobs, refetch, isLoading } = useQuery<EngagementJob[]>({
    queryKey: ['engagement-jobs', filterVideoId, uniqueVideos.map((v) => v.video_id).join(',')],
    queryFn: async () => {
      if (filterVideoId !== 'all') {
        return engagementApi.listJobsForVideo(filterVideoId) as Promise<EngagementJob[]>
      }
      const all = await Promise.all(
        uniqueVideos.map((v) =>
          engagementApi.listJobsForVideo(v.video_id).catch(() => []) as Promise<EngagementJob[]>
        )
      )
      // Belt-and-suspenders: dedupe by job_id in case the same record comes through twice.
      const byId = new Map<string, EngagementJob>()
      for (const job of all.flat()) byId.set(job.job_id, job)
      return [...byId.values()].sort((a, b) =>
        (b.created_at || '').localeCompare(a.created_at || '')
      )
    },
    enabled: !!videos,
    refetchInterval: (query) => {
      const data = query.state.data
      const hasActive = data?.some(
        (j) => j.status === EngagementJobStatus.PENDING || j.status === EngagementJobStatus.PROCESSING
      )
      return hasActive ? 3000 : false
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => engagementApi.deleteJob(jobId),
    onSuccess: () => {
      toast.success('Job deleted')
      refetch()
    },
  })

  const filteredJobs = useMemo(() => jobs || [], [jobs])

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold font-heading">Engagement Analysis</h1>
          <p className="mt-1 text-muted-foreground">
            Pair scene analysis with BARC data to find peaks and valleys
          </p>
        </div>
        {isMaster && (
          <Button asChild size="lg">
            <Link to="/engagement/new">
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              New Engagement Analysis
            </Link>
          </Button>
        )}
      </div>

      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total</CardDescription>
              <CardTitle className="text-3xl font-mono">{filteredJobs.length}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Active</CardDescription>
              <CardTitle className="text-3xl font-mono text-blue-600">
                {filteredJobs.filter((j) =>
                  j.status === EngagementJobStatus.PENDING ||
                  j.status === EngagementJobStatus.PROCESSING
                ).length}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completed</CardDescription>
              <CardTitle className="text-3xl font-mono text-green-600">
                {filteredJobs.filter((j) => j.status === EngagementJobStatus.COMPLETED).length}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Engagement Jobs</CardTitle>
                <CardDescription>{filteredJobs.length} job(s)</CardDescription>
              </div>
              <Select value={filterVideoId} onValueChange={setFilterVideoId}>
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder="Filter by video" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All videos</SelectItem>
                  {uniqueVideos.map((v) => (
                    <SelectItem key={v.video_id} value={v.video_id}>
                      <span className="block truncate">{v.filename}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-12 text-center text-muted-foreground">Loading…</div>
            ) : filteredJobs.length === 0 ? (
              <div className="py-12 text-center">
                <BarChart3 className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-semibold">No engagement analyses yet</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Upload a BARC CSV against a completed scene job to get started.
                </p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredJobs.map((job) => (
                  <EngagementJobCard
                    key={job.job_id}
                    job={job}
                    videoFilename={videoFilenames[job.video_id]}
                    onDelete={isMaster ? (id) => deleteMutation.mutate(id) : undefined}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
