import { useQuery, useMutation } from '@tanstack/react-query'
import { ArrowLeft, Trash2, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { mediaApi, videoApi, imageApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatBytes } from '@/lib/utils'
import { MediaJobStatus, ImageJobStatus } from '@/lib/types'
import { CreateAdapts } from '@/components/images/create-adapts'
import { AdaptResults } from '@/components/images/adapt-results'

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

  const getStatusBadge = (status: MediaJobStatus) => {
    switch (status) {
      case MediaJobStatus.COMPLETED:
        return (
          <Badge variant="default" className="bg-green-600">
            <CheckCircle className="mr-1 h-3 w-3" />
            Completed
          </Badge>
        )
      case MediaJobStatus.PROCESSING:
        const stepLabel = job?.progress?.step
          ? job.progress.step.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
          : 'Processing'
        return (
          <Badge variant="default" className="bg-blue-600">
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            {stepLabel}
          </Badge>
        )
      case MediaJobStatus.FAILED:
        return (
          <Badge variant="destructive">
            <XCircle className="mr-1 h-3 w-3" />
            Failed
          </Badge>
        )
      case MediaJobStatus.PENDING:
        return <Badge variant="outline">Pending</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
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
                  <CardTitle className="text-2xl">Media Processing Job</CardTitle>
                  <CardDescription className="mt-2">
                    Created {new Date(job.created_at || '').toLocaleString()}
                  </CardDescription>
                </div>
                {getStatusBadge(job.status)}
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

              {/* Progress */}
              {job.status === MediaJobStatus.PROCESSING && job.progress && (
                <div className="space-y-2 rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium capitalize">
                      {job.progress.step?.replace('_', ' ')}
                    </span>
                    <span className="font-semibold">{job.progress.percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className="h-full bg-blue-600 transition-all duration-300"
                      style={{ width: `${job.progress.percent}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Error */}
              {job.status === MediaJobStatus.FAILED && job.error_message && (
                <div className="rounded-lg bg-red-50 p-4 dark:bg-red-900/20">
                  <h4 className="font-semibold text-red-900 dark:text-red-100">Error</h4>
                  <p className="mt-1 text-sm text-red-800 dark:text-red-200">
                    {job.error_message}
                  </p>
                </div>
              )}
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

          {/* Results */}
          {job.status === MediaJobStatus.COMPLETED && job.results && (
            <Card>
              <CardHeader>
                <CardTitle>Results</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <dl className="grid gap-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="font-medium text-muted-foreground">Original Size</dt>
                    <dd className="font-medium">
                      {formatBytes(job.results.original_size_bytes)}
                    </dd>
                  </div>
                  {job.results.compressed_video_path && (
                    <>
                      <div className="flex justify-between">
                        <dt className="font-medium text-muted-foreground">Compressed Size</dt>
                        <dd className="font-medium">
                          {formatBytes(job.results.compressed_size_bytes)}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="font-medium text-muted-foreground">Size Reduction</dt>
                        <dd className="font-medium text-green-600 dark:text-green-400">
                          {job.results.compression_ratio.toFixed(1)}%
                        </dd>
                      </div>
                      <div className="col-span-full">
                        <dt className="font-medium text-muted-foreground">Compressed Video Path</dt>
                        <dd className="mt-1 break-all font-mono text-xs text-blue-600 dark:text-blue-400">
                          {job.results.compressed_video_path}
                        </dd>
                      </div>
                    </>
                  )}
                  {job.results.audio_path && (
                    <>
                      <div className="flex justify-between">
                        <dt className="font-medium text-muted-foreground">Audio Size</dt>
                        <dd className="font-medium">
                          {formatBytes(job.results.audio_size_bytes)}
                        </dd>
                      </div>
                      <div className="col-span-full">
                        <dt className="font-medium text-muted-foreground">Audio File Path</dt>
                        <dd className="mt-1 break-all font-mono text-xs text-blue-600 dark:text-blue-400">
                          {job.results.audio_path}
                        </dd>
                      </div>
                    </>
                  )}
                </dl>

                {/* Metadata Accordion */}
                {job.results.metadata && (
                  <details className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800">
                    <summary className="cursor-pointer font-medium">
                      View Full Metadata
                    </summary>
                    <pre className="mt-3 overflow-x-auto text-xs">
                      {JSON.stringify(job.results.metadata, null, 2)}
                    </pre>
                  </details>
                )}
              </CardContent>
            </Card>
          )}

          {/* Image Adaptation Section (Only for Images) */}
          {video?.source_type === 'image' && job.status === MediaJobStatus.COMPLETED && (
            <div className="space-y-6 pt-4">
              <div className="border-t pt-6">
                <h2 className="mb-4 text-2xl font-bold">Image Adaptation</h2>
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
