import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Languages,
  Plus,
  Play,
  Trash2,
  Sparkles,
  Clock,
  Mic,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Film,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { dubbingApi, videoApi } from '@/lib/api-client'
import { DubbingJob, DubbingJobStatus } from '@/lib/types'
import { toast } from 'sonner'

const LANGUAGE_FLAGS: Record<string, string> = {
  'hi-IN': '🇮🇳 Hindi',
  'en-US': '🇺🇸 English',
  'pt-BR': '🇧🇷 Portuguese',
  'es-ES': '🇪🇸 Spanish',
  'de-DE': '🇩🇪 German',
}

export default function DubbingPage() {
  const queryClient = useQueryClient()

  // Fetch all dubbing jobs
  const { data: jobs, isLoading, error } = useQuery<DubbingJob[]>({
    queryKey: ['dubbing-jobs'],
    queryFn: () => dubbingApi.listJobs(),
    refetchInterval: 4000,
  })

  // Fetch videos for name lookup
  const { data: videos } = useQuery({
    queryKey: ['videos-lookup'],
    queryFn: () => videoApi.listVideos(100),
  })

  const videoList: any[] = Array.isArray(videos) ? videos : Array.isArray((videos as any)?.items) ? (videos as any).items : []
  const videoMap = new Map<string, string>(videoList.map((v: any) => [v.video_id, v.filename || v.video_id]))

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => dubbingApi.deleteJob(jobId),
    onSuccess: () => {
      toast.success('Dubbing job deleted')
      queryClient.invalidateQueries({ queryKey: ['dubbing-jobs'] })
    },
    onError: (err: any) => {
      toast.error('Failed to delete job', {
        description: err.response?.data?.detail || err.message,
      })
    },
  })

  const completedJobsCount = jobs?.filter((j) => j.status === DubbingJobStatus.COMPLETED).length || 0
  const processingJobsCount = jobs?.filter((j) => j.status !== DubbingJobStatus.COMPLETED && j.status !== DubbingJobStatus.FAILED).length || 0

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
              <Languages className="h-7 w-7" />
            </div>
            <div>
              <h1 className="text-3xl font-bold font-heading">AI Video Dubbing Studio</h1>
              <p className="text-muted-foreground text-sm mt-0.5">
                Multimodal speech translation & synchronized voice synthesis for Hindi, Spanish, Portuguese, German, and English.
              </p>
            </div>
          </div>
        </div>

        <Button asChild className="gap-2 shadow-lg">
          <Link to="/dubbing/new">
            <Plus className="h-4 w-4" />
            <span>New Dubbing Job</span>
          </Link>
        </Button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center justify-between bg-card/60 backdrop-blur-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Dubbed Jobs</p>
            <p className="text-2xl font-bold font-heading mt-1">{jobs?.length || 0}</p>
          </div>
          <Film className="h-8 w-8 text-primary/40" />
        </Card>

        <Card className="p-4 flex items-center justify-between bg-card/60 backdrop-blur-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Completed Tracks</p>
            <p className="text-2xl font-bold font-heading mt-1 text-emerald-500">{completedJobsCount}</p>
          </div>
          <CheckCircle2 className="h-8 w-8 text-emerald-500/40" />
        </Card>

        <Card className="p-4 flex items-center justify-between bg-card/60 backdrop-blur-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Active Processing</p>
            <p className="text-2xl font-bold font-heading mt-1 text-amber-500">{processingJobsCount}</p>
          </div>
          <Loader2 className={`h-8 w-8 text-amber-500/40 ${processingJobsCount > 0 ? 'animate-spin' : ''}`} />
        </Card>
      </div>

      {/* Jobs Listing */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse h-48 bg-muted/40" />
          ))}
        </div>
      ) : jobs && jobs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {jobs.map((job) => {
            const videoName = videoMap.get(job.video_id) || job.video_id
            const targetLangs = job.config?.target_languages || []
            const isCompleted = job.status === DubbingJobStatus.COMPLETED
            const isFailed = job.status === DubbingJobStatus.FAILED

            return (
              <Card
                key={job.job_id}
                className="flex flex-col justify-between overflow-hidden border-border hover:border-primary/50 transition-all shadow-sm group"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="truncate flex-1">
                      <CardTitle className="text-base font-heading truncate" title={videoName}>
                        {videoName}
                      </CardTitle>
                      <CardDescription className="text-xs truncate mt-0.5">
                        Voice: <span className="font-semibold">{job.config?.voice || 'Kore'}</span> • Mode: {job.config?.mode || 'Voiceover'}
                      </CardDescription>
                    </div>

                    <Badge
                      variant={isCompleted ? 'default' : isFailed ? 'destructive' : 'secondary'}
                      className="capitalize text-[11px] gap-1 shrink-0"
                    >
                      {!isCompleted && !isFailed && <Loader2 className="h-3 w-3 animate-spin" />}
                      {job.status.replace('_', ' ')}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4 pt-0">
                  {/* Language Badges */}
                  <div>
                    <p className="text-[11px] text-muted-foreground uppercase tracking-wider font-semibold mb-1.5">
                      Dubbing Tracks:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {targetLangs.map((lang) => (
                        <Badge key={lang} variant="outline" className="text-xs bg-muted/40 font-normal">
                          {LANGUAGE_FLAGS[lang] || lang}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {job.error_message && (
                    <div className="text-xs text-destructive bg-destructive/10 p-2 rounded-md flex items-center gap-1.5">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{job.error_message}</span>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {job.created_at ? new Date(job.created_at).toLocaleDateString() : 'Recent'}
                    </span>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:bg-destructive/10"
                        onClick={(e) => {
                          e.preventDefault()
                          if (confirm('Delete this dubbing job?')) {
                            deleteJobMutation.mutate(job.job_id)
                          }
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>

                      <Link to={`/dubbing/${job.job_id}`}>
                        <Button size="sm" className="h-8 gap-1.5 text-xs">
                          <Play className="h-3.5 w-3.5" />
                          <span>Preview Player</span>
                        </Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : (
        <Card className="py-16 text-center border-dashed">
          <CardContent className="space-y-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <Languages className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-lg font-semibold font-heading">No dubbing jobs yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto mt-1">
                Translate any uploaded video into Hindi, Spanish, Portuguese, German, or English with synchronized speech.
              </p>
            </div>
            <Button asChild className="gap-2">
              <Link to="/dubbing/new">
                <Plus className="h-4 w-4" />
                <span>Create First Dubbing Job</span>
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
