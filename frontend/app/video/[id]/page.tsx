'use client'

import { use } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Play, Download } from 'lucide-react'
import Link from 'next/link'
import { videoApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { formatBytes, formatDuration } from '@/lib/utils'

export default function VideoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)

  const { data: video, isLoading } = useQuery({
    queryKey: ['video', id],
    queryFn: () => videoApi.getVideo(id),
    refetchInterval: (query) => {
      // Auto-refresh if video is processing or analyzing
      if (query.state.data && (query.state.data.status === 'processing' || query.state.data.status === 'analyzing')) {
        return 3000 // 3 seconds
      }
      return false
    },
  })

  const { data: manifest } = useQuery({
    queryKey: ['manifest', id],
    queryFn: () => videoApi.getManifest(id),
    enabled: video?.status === 'processed' || video?.status === 'analyzing' || video?.status === 'completed',
  })

  const { data: results } = useQuery({
    queryKey: ['results', id],
    queryFn: () => videoApi.getResults(id),
    enabled: video?.status === 'completed',
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

  if (!video) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold">Video not found</h2>
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
                <CardTitle className="text-2xl">{video.filename}</CardTitle>
                <CardDescription>
                  Status: {video.status}
                  {video.size_bytes && ` • ${formatBytes(video.size_bytes)}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <dt className="text-sm font-medium text-muted-foreground">Video ID</dt>
                    <dd className="mt-1 text-sm font-mono">{video.video_id}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-muted-foreground">Content Type</dt>
                    <dd className="mt-1 text-sm">{video.content_type || 'N/A'}</dd>
                  </div>
                  {video.metadata?.duration && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Duration</dt>
                      <dd className="mt-1 text-sm">{formatDuration(video.metadata.duration)}</dd>
                    </div>
                  )}
                  {video.metadata?.video && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Resolution</dt>
                      <dd className="mt-1 text-sm">
                        {video.metadata.video.width} × {video.metadata.video.height}
                      </dd>
                    </div>
                  )}
                  {video.error_message && (
                    <div className="col-span-full">
                      <dt className="text-sm font-medium text-destructive">Error</dt>
                      <dd className="mt-1 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                        {video.error_message}
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

          {/* Sidebar */}
          <div className="space-y-6">
            {(video.status === 'processed' || video.status === 'failed' || video.status === 'uploaded') && (
              <Card>
                <CardHeader>
                  <CardTitle>Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {video.status === 'processed' && (
                    <Button
                      className="w-full"
                      onClick={() => videoApi.analyzeVideo(video.video_id)}
                    >
                      <Play className="mr-2 h-4 w-4" />
                      Start Analysis
                    </Button>
                  )}
                  {video.status === 'failed' && (
                    <p className="text-sm text-muted-foreground">
                      Processing failed. Please delete and re-upload the video.
                    </p>
                  )}
                  {video.status === 'uploaded' && (
                    <p className="text-sm text-muted-foreground">
                      Video uploaded successfully. Processing will start automatically.
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
