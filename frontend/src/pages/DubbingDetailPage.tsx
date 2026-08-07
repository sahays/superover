import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ArrowLeft,
  Trash2,
  Languages,
  Clock,
  Sparkles,
  CheckCircle2,
  Loader2,
  FileAudio,
  Film,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { dubbingApi, videoApi } from '@/lib/api-client'
import { DubbingJob, DubbingJobStatus } from '@/lib/types'
import { DubbedVideoPlayer } from '@/components/dubbing/dubbed-video-player'
import { toast } from 'sonner'

const STEP_ORDER = [
  { key: DubbingJobStatus.PENDING, label: 'Submitted' },
  { key: DubbingJobStatus.EXTRACTING_AUDIO, label: 'Audio Extract' },
  { key: DubbingJobStatus.DUBBING_TRANSLATION, label: 'Gemini Translation' },
  { key: DubbingJobStatus.GENERATING_SPEECH, label: 'Voice Synthesis' },
  { key: DubbingJobStatus.MUXING_VIDEO, label: 'Video Muxing' },
  { key: DubbingJobStatus.COMPLETED, label: 'Ready' },
]

export default function DubbingDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()

  // Fetch dubbing job details with polling during processing
  const { data: job, isLoading, refetch } = useQuery<DubbingJob>({
    queryKey: ['dubbing-job-detail', jobId],
    queryFn: () => dubbingApi.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && status !== DubbingJobStatus.COMPLETED && status !== DubbingJobStatus.FAILED) {
        return 3000
      }
      return false
    },
  })

  // Fetch original video info
  const { data: video } = useQuery({
    queryKey: ['video-info-for-dubbing', job?.video_id],
    queryFn: () => videoApi.getVideo(job!.video_id),
    enabled: !!job?.video_id,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => dubbingApi.deleteJob(id),
    onSuccess: () => {
      toast.success('Dubbing job deleted')
      navigate('/dubbing')
    },
    onError: (err: any) => {
      toast.error('Failed to delete job', {
        description: err.response?.data?.detail || err.message,
      })
    },
  })

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 rounded bg-muted" />
          <div className="h-96 rounded bg-muted" />
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <Card className="py-12 text-center">
          <CardContent className="space-y-4">
            <h2 className="text-xl font-semibold">Dubbing Job Not Found</h2>
            <Link to="/dubbing">
              <Button variant="outline" className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back to Dubbing Studio
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  const isCompleted = job.status === DubbingJobStatus.COMPLETED
  const isFailed = job.status === DubbingJobStatus.FAILED
  const activeStepIdx = STEP_ORDER.findIndex((s) => s.key === job.status)

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl space-y-6">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <Link to="/dubbing">
          <Button variant="ghost" size="sm" className="gap-2 -ml-2">
            <ArrowLeft className="h-4 w-4" />
            <span>Dubbing Studio</span>
          </Button>
        </Link>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:bg-destructive/10 gap-2"
            onClick={() => {
              if (confirm('Delete this dubbing job and associated tracks?')) {
                deleteMutation.mutate(job.job_id)
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
            <span>Delete Job</span>
          </Button>
        </div>
      </div>

      {/* Main Info Card */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle className="text-2xl font-heading">
                {video?.filename || `Video: ${job.video_id}`}
              </CardTitle>
              <CardDescription className="text-xs mt-1">
                Job ID: <code className="font-mono">{job.job_id}</code> • Voice Persona:{' '}
                <span className="font-semibold text-foreground">{job.config?.voice || 'Kore'}</span>
              </CardDescription>
            </div>

            <Badge
              variant={isCompleted ? 'default' : isFailed ? 'destructive' : 'secondary'}
              className="capitalize text-sm py-1 px-3 gap-1.5 self-start sm:self-auto"
            >
              {!isCompleted && !isFailed && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {job.status.replace('_', ' ')}
            </Badge>
          </div>
        </CardHeader>

        {/* Processing Stepper */}
        {!isCompleted && !isFailed && (
          <CardContent className="pt-0">
            <div className="p-4 bg-muted/40 rounded-lg border space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <span>Pipeline Progress</span>
                <span className="text-primary capitalize">{job.status.replace('_', ' ')}...</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
                {STEP_ORDER.map((step, idx) => {
                  const isDone = activeStepIdx > idx
                  const isCurrent = activeStepIdx === idx
                  return (
                    <div
                      key={step.key}
                      className={`p-2 rounded border text-center text-xs transition-all ${
                        isDone
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600'
                          : isCurrent
                          ? 'bg-primary/10 border-primary text-primary font-semibold ring-1 ring-primary'
                          : 'bg-background/50 border-border text-muted-foreground opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-center gap-1 mb-0.5">
                        {isDone ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : isCurrent ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <span className="h-3 w-3 rounded-full border text-[9px] flex items-center justify-center">
                            {idx + 1}
                          </span>
                        )}
                      </div>
                      <span className="truncate block">{step.label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Interactive Video Player & Script Comparison */}
      <DubbedVideoPlayer job={job} />

      {/* Generated Track Details Table */}
      {isCompleted && Object.keys(job.tracks || {}).length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-heading flex items-center gap-2">
              <Film className="h-4 w-4 text-primary" />
              Generated Language Renditions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y rounded-md border">
              {Object.entries(job.tracks).map(([lang, track]) => (
                <div key={lang} className="p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 hover:bg-muted/20 transition-colors">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{track.language_label || lang}</span>
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {lang}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Segments: {track.segments?.length || 0} • Duration: {track.duration_seconds?.toFixed(1) || 0}s
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {track.audio_gcs_path && (
                      <Badge variant="secondary" className="text-xs gap-1">
                        <FileAudio className="h-3 w-3" />
                        Audio Track Synced
                      </Badge>
                    )}
                    {track.video_gcs_path && (
                      <Badge variant="default" className="text-xs gap-1">
                        <Film className="h-3 w-3" />
                        Muxed MP4 Ready
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
