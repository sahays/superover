'use client'

import { use, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { ArrowLeft, Play, Download, Settings } from 'lucide-react'
import Link from 'next/link'
import { videoApi, mediaApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { formatBytes, formatDuration } from '@/lib/utils'
import { StartProcessing } from '@/components/media/start-processing'
import { JobCard } from '@/components/media/job-card'

export default function SceneDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [showMediaDialog, setShowMediaDialog] = useState(false)

  const { data: scene, isLoading } = useQuery({
    queryKey: ['scene', id],
    queryFn: () => videoApi.getVideo(id),
    refetchInterval: (query) => {
      // Auto-refresh if scene is processing or analyzing
      if (query.state.data && (query.state.data.status === 'processing' || query.state.data.status === 'analyzing')) {
        return 3000 // 3 seconds
      }
      return false
    },
  })

  const { data: manifest } = useQuery({
    queryKey: ['manifest', id],
    queryFn: () => videoApi.getManifest(id),
    enabled: scene?.status === 'processed' || scene?.status === 'analyzing' || scene?.status === 'completed',
  })

  const { data: results } = useQuery({
    queryKey: ['results', id],
    queryFn: () => videoApi.getResults(id),
    enabled: scene?.status === 'completed',
  })

  const { data: mediaJobs, refetch: refetchMediaJobs } = useQuery({
    queryKey: ['media-jobs', id],
    queryFn: () => mediaApi.listJobsForVideo(id),
    refetchInterval: 5000, // Poll every 5 seconds
  })

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => mediaApi.deleteJob(jobId),
    onSuccess: () => {
      refetchMediaJobs()
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

  if (!scene) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold">Scene not found</h2>
            <Link href="/">
              <Button className="mt-4" variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Home
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="container mx-auto max-w-6xl px-4 py-8">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <Link href="/">
            <Button variant="ghost">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main Info */}
          <div className="space-y-6 lg:col-span-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-2xl">{scene.filename}</CardTitle>
                <CardDescription>
                  Status: {scene.status}
                  {scene.size_bytes && ` • ${formatBytes(scene.size_bytes)}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <dt className="text-sm font-medium text-muted-foreground">Scene ID</dt>
                    <dd className="mt-1 text-sm font-mono">{scene.video_id}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-muted-foreground">Content Type</dt>
                    <dd className="mt-1 text-sm">{scene.content_type || 'N/A'}</dd>
                  </div>
                  {scene.metadata?.duration && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Duration</dt>
                      <dd className="mt-1 text-sm">{formatDuration(scene.metadata.duration)}</dd>
                    </div>
                  )}
                  {scene.metadata?.video && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Resolution</dt>
                      <dd className="mt-1 text-sm">
                        {scene.metadata.video.width} × {scene.metadata.video.height}
                      </dd>
                    </div>
                  )}
                  {scene.error_message && (
                    <div className="col-span-full">
                      <dt className="text-sm font-medium text-destructive">Error</dt>
                      <dd className="mt-1 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                        {scene.error_message}
                      </dd>
                    </div>
                  )}
                </dl>
              </CardContent>
            </Card>

            {/* Manifest */}
            {manifest && (
              <Card>
                <CardHeader>
                  <CardTitle>Processing Info</CardTitle>
                </CardHeader>
                <CardContent>
                  <Accordion type="single" collapsible className="w-full">
                    {manifest.chunks && (
                      <AccordionItem value="chunks">
                        <AccordionTrigger>
                          Chunks ({manifest.chunks.count})
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">
                              {manifest.chunks.count} chunks × {manifest.chunks.duration_per_chunk}s each
                            </p>
                            {manifest.chunks.items && (
                              <div className="space-y-1">
                                {manifest.chunks.items.map((chunk: any, idx: number) => (
                                  <div key={idx} className="text-xs font-mono text-muted-foreground">
                                    Chunk {idx}: {chunk.filename}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    )}
                    {manifest.compressed && (
                      <AccordionItem value="compressed">
                        <AccordionTrigger>Compressed Video</AccordionTrigger>
                        <AccordionContent>
                          <p className="text-sm text-muted-foreground font-mono break-all">
                            {manifest.compressed.gcs_path}
                          </p>
                        </AccordionContent>
                      </AccordionItem>
                    )}
                    {manifest.audio && (
                      <AccordionItem value="audio">
                        <AccordionTrigger>Audio</AccordionTrigger>
                        <AccordionContent>
                          <p className="text-sm text-muted-foreground font-mono break-all">
                            {manifest.audio.gcs_path}
                          </p>
                        </AccordionContent>
                      </AccordionItem>
                    )}
                  </Accordion>
                </CardContent>
              </Card>
            )}

            {/* Results */}
            {results && results.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Scene Analysis</CardTitle>
                  <CardDescription>{results.length} chunks analyzed</CardDescription>
                </CardHeader>
                <CardContent>
                  <Accordion type="single" collapsible className="w-full">
                    {results.map((result: any, idx: number) => (
                      <AccordionItem key={result.result_id} value={`result-${idx}`}>
                        <AccordionTrigger>
                          {result.result_type.replace('_', ' ')} - Chunk {idx}
                        </AccordionTrigger>
                        <AccordionContent>
                          <pre className="overflow-x-auto rounded bg-slate-100 p-3 text-xs dark:bg-slate-800">
                            {JSON.stringify(result.result_data, null, 2)}
                          </pre>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Media Processing Jobs */}
          {mediaJobs && mediaJobs.length > 0 && (
            <div className="lg:col-span-3">
              <Card>
                <CardHeader>
                  <CardTitle>Media Processing Jobs</CardTitle>
                  <CardDescription>{mediaJobs.length} job(s) total</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {mediaJobs.map((job: any, idx: number) => (
                      <div key={job.job_id} className="border rounded-lg">
                        <div className="flex items-center justify-between w-full p-4">
                          <span className="font-semibold">Job {idx + 1} - {job.status}</span>
                          <span className="text-sm text-muted-foreground">
                            {new Date(job.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <div className="space-y-4 p-4 border-t">
                          {/* Job ID and Timestamps */}
                          <div className="grid gap-3 text-sm">
                            <div className="flex justify-between">
                              <span className="font-medium text-muted-foreground">Job ID:</span>
                              <span className="font-mono text-xs">{job.job_id}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="font-medium text-muted-foreground">Created:</span>
                              <span>{new Date(job.created_at).toLocaleString()}</span>
                            </div>
                            {job.updated_at && (
                              <div className="flex justify-between">
                                <span className="font-medium text-muted-foreground">Updated:</span>
                                <span>{new Date(job.updated_at).toLocaleString()}</span>
                              </div>
                            )}
                          </div>

                          {/* Configuration */}
                          <div className="rounded-lg bg-slate-100 p-3 dark:bg-slate-800">
                            <h4 className="font-semibold mb-2">Configuration</h4>
                            <div className="grid gap-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Compression:</span>
                                <span>{job.config.compress ? job.config.compress_resolution : 'Disabled'}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">CRF:</span>
                                <span>{job.config.crf}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Preset:</span>
                                <span>{job.config.preset}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Audio:</span>
                                <span>
                                  {job.config.extract_audio
                                    ? `${job.config.audio_format?.toUpperCase()} @ ${job.config.audio_bitrate}`
                                    : 'Disabled'}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Results */}
                          {job.results && (
                            <div className="rounded-lg bg-green-50 p-3 dark:bg-green-900/20">
                              <h4 className="font-semibold mb-2 text-green-900 dark:text-green-100">Results</h4>
                              <div className="grid gap-2 text-sm">
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Original Size:</span>
                                  <span className="font-medium">{formatBytes(job.results.original_size_bytes)}</span>
                                </div>
                                {job.results.compressed_video_path && (
                                  <>
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">Compressed Size:</span>
                                      <span className="font-medium">{formatBytes(job.results.compressed_size_bytes)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">Reduction:</span>
                                      <span className="font-medium text-green-600 dark:text-green-400">
                                        {job.results.compression_ratio.toFixed(1)}%
                                      </span>
                                    </div>
                                    <div className="col-span-full">
                                      <span className="text-muted-foreground">Compressed File:</span>
                                      <p className="mt-1 font-mono text-xs break-all text-blue-600 dark:text-blue-400">
                                        {job.results.compressed_video_path}
                                      </p>
                                    </div>
                                  </>
                                )}
                                {job.results.audio_path && (
                                  <>
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">Audio Size:</span>
                                      <span className="font-medium">{formatBytes(job.results.audio_size_bytes)}</span>
                                    </div>
                                    <div className="col-span-full">
                                      <span className="text-muted-foreground">Audio File:</span>
                                      <p className="mt-1 font-mono text-xs break-all text-blue-600 dark:text-blue-400">
                                        {job.results.audio_path}
                                      </p>
                                    </div>
                                  </>
                                )}
                                {job.results.metadata && (
                                  <details className="col-span-full mt-2">
                                    <summary className="cursor-pointer text-muted-foreground">
                                      View Full Metadata
                                    </summary>
                                    <pre className="mt-2 overflow-x-auto rounded bg-slate-200 p-2 text-xs dark:bg-slate-900">
                                      {JSON.stringify(job.results.metadata, null, 2)}
                                    </pre>
                                  </details>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Error */}
                          {job.error_message && (
                            <div className="rounded-lg bg-red-50 p-3 dark:bg-red-900/20">
                              <h4 className="font-semibold mb-2 text-red-900 dark:text-red-100">Error</h4>
                              <p className="text-sm text-red-800 dark:text-red-200">{job.error_message}</p>
                            </div>
                          )}

                          {/* Actions */}
                          {job.status !== 'processing' && (
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => {
                                if (confirm('Delete this job and all generated files? The original video will not be deleted.')) {
                                  deleteJobMutation.mutate(job.job_id)
                                }
                              }}
                            >
                              Delete Job & Files
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
