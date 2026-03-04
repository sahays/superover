import { useQuery, useMutation } from '@tanstack/react-query'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { mediaApi, videoApi, imageApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { MediaJobStatus, ImageJobStatus } from '@/lib/types'
import { CreateAdapts } from '@/components/images/create-adapts'
import { AdaptResults } from '@/components/images/adapt-results'
import { getMediaStatusBadge } from '@/lib/media-status'
import { JobProgressSection } from '@/components/media/job-progress-section'
import { JobResultsCard } from '@/components/media/job-results-card'

export default function MediaJobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()

  const { data: job, isLoading } = useQuery({
    queryKey: ['media-job', jobId],
    queryFn: () => mediaApi.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      // Auto-refresh if job is processing
      if (query.state.data && query.state.data.status === MediaJobStatus.PROCESSING) {
        return 3000 // 3 seconds
      }
      return false
    },
  })

  const { data: video } = useQuery({
    queryKey: ['video', job?.video_id],
    queryFn: () => videoApi.getVideo(job!.video_id),
    enabled: !!job?.video_id,
  })

  const { data: imageJobs, refetch: refetchImageJobs } = useQuery({
    queryKey: ['image-jobs', job?.video_id],
    queryFn: () => imageApi.listJobsForAsset(job!.video_id),
    enabled: !!job?.video_id && video?.source_type === 'image',
  })

  const deleteJobMutation = useMutation({
    mutationFn: (id: string) => mediaApi.deleteJob(id),
    onSuccess: () => {
      navigate('/media')
    },
  })

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 rounded bg-gray-200" />
          <div className="h-64 rounded bg-gray-200" />
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold">Media job not found</h2>
            <Link to="/media">
              <Button className="mt-4" variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Media Processing
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)]">
      <div className="container mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <Link to="/media">
            <Button variant="ghost">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Media Processing
            </Button>
          </Link>
        </div>

        <div className="space-y-6">
          {/* Job Info */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl font-heading">Media Processing Job</CardTitle>
                  <CardDescription className="mt-2">
                    Created {new Date(job.created_at || '').toLocaleString()}
                  </CardDescription>
                </div>
                {getMediaStatusBadge(job.status, job.progress)}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid gap-3 text-sm">
                <div>
                  <dt className="font-medium text-muted-foreground">Job ID</dt>
                  <dd className="mt-1 font-mono text-xs">{job.job_id}</dd>
                </div>
                <div>
                  <dt className="font-medium text-muted-foreground">Video ID</dt>
                  <dd className="mt-1 font-mono text-xs">{job.video_id}</dd>
                </div>
                {video && (
                  <div>
                    <dt className="font-medium text-muted-foreground">Video File</dt>
                    <dd className="mt-1">{video.filename}</dd>
                  </div>
                )}
                {job.updated_at && (
                  <div>
                    <dt className="font-medium text-muted-foreground">Last Updated</dt>
                    <dd className="mt-1">{new Date(job.updated_at).toLocaleString()}</dd>
                  </div>
                )}
              </dl>

              <JobProgressSection
                status={job.status}
                progress={job.progress}
                errorMessage={job.error_message}
              />
            </CardContent>
          </Card>

          {/* Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                {/* Only show compression settings if there's a video stream in the source */}
                {video?.metadata?.video && (
                  <>
                    <div>
                      <dt className="font-medium text-muted-foreground">Compression</dt>
                      <dd className="mt-1">
                        {job.config.compress ? job.config.compress_resolution : 'Disabled'}
                      </dd>
                    </div>
                    {job.config.compress && (
                      <>
                        <div>
                          <dt className="font-medium text-muted-foreground">CRF</dt>
                          <dd className="mt-1">{job.config.crf}</dd>
                        </div>
                      </>
                    )}
                  </>
                )}
                <div>
                  <dt className="font-medium text-muted-foreground">Audio Extraction</dt>
                  <dd className="mt-1">
                    {job.config.extract_audio
                      ? `${job.config.audio_format?.toUpperCase()} @ ${job.config.audio_bitrate}`
                      : 'Disabled'}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {job.status === MediaJobStatus.COMPLETED && job.results && (
            <JobResultsCard results={job.results} />
          )}

          {/* Image Adaptation Section (Only for Images) */}
          {video?.source_type === 'image' && job.status === MediaJobStatus.COMPLETED && (
            <div className="space-y-6 pt-4">
              <div className="border-t pt-6">
                <h2 className="mb-4 text-2xl font-bold font-heading">Image Adaptation</h2>
                <CreateAdapts
                  videoId={job.video_id}
                  onJobCreated={() => refetchImageJobs()}
                />
              </div>

              {imageJobs?.map((imgJob: any) => (
                <div key={imgJob.job_id} className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-medium">Job: {imgJob.job_id.slice(0, 8)}</h3>
                    <Badge variant={imgJob.status === 'completed' ? 'default' : 'outline'}>
                      {imgJob.status}
                    </Badge>
                  </div>
                  <AdaptResults jobId={imgJob.job_id} status={imgJob.status as ImageJobStatus} />
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          {job.status !== MediaJobStatus.PROCESSING && (
            <Card>
              <CardContent className="pt-6">
                <Button
                  variant="destructive"
                  onClick={() => {
                    if (
                      confirm(
                        'Delete this job and all generated files? The original video will not be deleted.'
                      )
                    ) {
                      deleteJobMutation.mutate(job.job_id)
                    }
                  }}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Job & Files
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
