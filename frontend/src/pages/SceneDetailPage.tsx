import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, FileJson, FileSpreadsheet, Coins } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { videoApi, sceneJobApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { formatBytes, formatDuration } from '@/lib/utils'
import { generateSceneCSV, generateSceneJSON, downloadFile } from '@/lib/scene-export'

export default function SceneDetailPage() {
  const { id: jobId } = useParams<{ id: string }>()

  // First get the scene job
  const { data: sceneJob, isLoading: isLoadingJob } = useQuery({
    queryKey: ['scene-job', jobId],
    queryFn: () => sceneJobApi.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      // Auto-refresh if scene job is processing
      const status = query.state.data?.status
      return status === 'pending' || status === 'processing' ? 3000 : false
    },
  })

  const videoId = sceneJob?.video_id

  // Get video metadata
  const { data: scene, isLoading: isLoadingVideo } = useQuery({
    queryKey: ['scene', videoId],
    queryFn: () => videoApi.getVideo(videoId!),
    enabled: !!videoId,
  })

  const isLoading = isLoadingJob || isLoadingVideo

  // Check if job is completed
  const isCompleted = sceneJob?.status === 'completed'

  const { data: manifest } = useQuery({
    queryKey: ['manifest', videoId],
    queryFn: () => videoApi.getManifest(videoId!),
    enabled: !!videoId && isCompleted,
  })

  const { data: results } = useQuery({
    queryKey: ['results', jobId],
    queryFn: () => sceneJobApi.getResults(jobId!),
    enabled: isCompleted,
  })

  // Calculate totals
  const totalTokens = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.total_tokens || 0), 0) || 0
  const totalCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.estimated_cost_usd || 0), 0) || 0
  const totalInputCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.input_cost_usd || 0), 0) || 0
  const totalOutputCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.output_cost_usd || 0), 0) || 0

  const getDownloadFilename = (extension: string) => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19).replace('T', '-')
    const baseFilename = scene?.filename ? scene.filename.replace(/\.[^/.]+$/, '') : 'scene'
    const promptName = sceneJob?.prompt_name
      ? sceneJob.prompt_name.replace(/[^a-zA-Z0-9]/g, '_')
      : (sceneJob?.prompt_type || 'analysis')

    return `${baseFilename}_${promptName}_${timestamp}.${extension}`
  }

  const downloadAsJSON = () => {
    if (!results || !sceneJob || !jobId) return

    const chunkDuration = sceneJob.config.chunk_duration || 0
    const jsonData = generateSceneJSON(
      results,
      chunkDuration,
      jobId,
      sceneJob.video_id,
      scene?.filename
    )

    downloadFile(jsonData, getDownloadFilename('json'), 'json')
  }

  const downloadAsCSV = () => {
    if (!results || !sceneJob) return

    const chunkDuration = sceneJob.config.chunk_duration || 0
    const csvContent = generateSceneCSV(results, chunkDuration)

    downloadFile(csvContent, getDownloadFilename('csv'), 'csv')
  }



  // Check if this is a subtitle job
  const isSubtitleJob = results && results.length > 0 &&
    (results[0].result_data?.prompt_type === 'subtitling' ||
     results[0].result_data?.prompt_type === 'transcription')

  const downloadAsSRT = () => {
    if (!results) return

    // Combine all subtitle texts from all chunks
    const srtContent = results
      .map((result: any) => result.result_data?.subtitle_text)
      .filter((text: string) => text)
      .join('\n\n')

    downloadFile(srtContent, getDownloadFilename('srt'), 'srt')
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

  if (!scene) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold">Scene not found</h2>
            <Link to="/">
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
          <Link to="/scene-analysis">
            <Button variant="ghost">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Scene Analysis
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
                        {scene.metadata.video.width} x {scene.metadata.video.height}
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

            {/* Scene Job Info */}
            {sceneJob && (
              <Card>
                <CardHeader>
                  <CardTitle>Scene Analysis Job</CardTitle>
                  <CardDescription>Configuration and status for this analysis</CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Job ID</dt>
                      <dd className="mt-1 text-sm font-mono">{sceneJob.job_id}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Status</dt>
                      <dd className="mt-1 text-sm capitalize">{sceneJob.status}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Est. Cost</dt>
                      <dd className={`mt-1 text-sm font-medium flex flex-wrap items-center gap-1 ${totalCost > 0 ? 'text-green-600' : 'text-muted-foreground'}`}>
                        {totalCost > 0 ? (
                          <>
                            <div className="flex items-center gap-1">
                              <Coins className="h-3.5 w-3.5" />
                              ${totalCost.toFixed(4)}
                            </div>
                            {(totalInputCost > 0 || totalOutputCost > 0) && (
                              <span className="text-xs font-normal text-muted-foreground ml-1">
                                (In: ${totalInputCost.toFixed(4)} | Out: ${totalOutputCost.toFixed(4)})
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="text-muted-foreground font-normal">N/A (Historical)</span>
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Total Tokens</dt>
                      <dd className="mt-1 text-sm">
                        {totalTokens > 0 ? totalTokens.toLocaleString() : <span className="text-muted-foreground">N/A</span>}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Chunk Duration</dt>
                      <dd className="mt-1 text-sm">
                        {sceneJob.config.chunk_duration > 0
                          ? `${sceneJob.config.chunk_duration}s`
                          : 'No chunking (full video)'}
                      </dd>
                    </div>
                    {sceneJob.config.compressed_video_path && (
                      <div>
                        <dt className="text-sm font-medium text-muted-foreground">Source</dt>
                        <dd className="mt-1 text-sm">Compressed video from media workflow</dd>
                      </div>
                    )}
                    {sceneJob.results && (
                      <div className="col-span-full">
                        <dt className="text-sm font-medium text-muted-foreground">Results</dt>
                        <dd className="mt-1 text-sm">
                          {sceneJob.results.chunks_analyzed} chunk(s) analyzed
                          {sceneJob.results.manifest_created && ' • Manifest created'}
                        </dd>
                      </div>
                    )}
                    {sceneJob.error_message && (
                      <div className="col-span-full">
                        <dt className="text-sm font-medium text-destructive">Error</dt>
                        <dd className="mt-1 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                          {sceneJob.error_message}
                        </dd>
                      </div>
                    )}
                  </dl>
                </CardContent>
              </Card>
            )}

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
                              {manifest.chunks.count} chunks x {manifest.chunks.duration_per_chunk}s each
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
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>{isSubtitleJob ? 'Subtitles' : 'Scene Analysis'}</CardTitle>
                      <CardDescription>
                        {results.length} chunk(s) analyzed
                        {isSubtitleJob && results.length > 0 && (
                          <span className="ml-2">
                            • {results.reduce((sum: number, r: any) =>
                              sum + (r.result_data?.subtitle_text?.length || 0), 0).toLocaleString()} characters
                          </span>
                        )}
                      </CardDescription>
                    </div>
                    {isSubtitleJob ? (
                      <Button variant="outline" size="sm" onClick={downloadAsSRT}>
                        <Download className="mr-2 h-4 w-4" />
                        Download SRT
                      </Button>
                    ) : (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="outline" size="sm">
                            <Download className="mr-2 h-4 w-4" />
                            Download All
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={downloadAsJSON}>
                            <FileJson className="mr-2 h-4 w-4" />
                            Download as JSON
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={downloadAsCSV}>
                            <FileSpreadsheet className="mr-2 h-4 w-4" />
                            Download as CSV
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <Accordion type="single" collapsible className="w-full">
                    {results.map((result: any, idx: number) => {
                      const isSubtitle = result.result_data?.prompt_type === 'subtitling' || result.result_data?.prompt_type === 'transcription'
                      const subtitleText = result.result_data?.subtitle_text

                      return (
                        <AccordionItem key={result.result_id} value={`result-${idx}`}>
                          <AccordionTrigger>
                            <div className="flex gap-2 items-center">
                              <span>{result.result_type.replace('_', ' ')} - Chunk {idx}</span>
                              {result.result_data?.token_usage?.estimated_cost_usd !== undefined && (
                                <span className="text-xs font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                  ${result.result_data.token_usage.estimated_cost_usd.toFixed(4)}
                                </span>
                              )}
                              {isSubtitle && <span className="text-xs text-muted-foreground">(Subtitles)</span>}
                            </div>
                          </AccordionTrigger>
                          <AccordionContent>
                            {result.result_data?.token_usage && (
                              <div className="mb-4 text-xs text-muted-foreground flex gap-4 border-b pb-2">
                                <div>
                                  Prompt Tokens: <span className="font-mono">{result.result_data.token_usage.prompt_tokens?.toLocaleString()}</span>
                                  {result.result_data.token_usage.applied_input_rate && (
                                    <span className="ml-1 opacity-70">(@ ${result.result_data.token_usage.applied_input_rate.toFixed(2)}/1M)</span>
                                  )}
                                </div>
                                <div>
                                  Output Tokens: <span className="font-mono">{result.result_data.token_usage.candidates_tokens?.toLocaleString()}</span>
                                  {result.result_data.token_usage.applied_output_rate && (
                                    <span className="ml-1 opacity-70">(@ ${result.result_data.token_usage.applied_output_rate.toFixed(2)}/1M)</span>
                                  )}
                                </div>
                                <div>Total: <span className="font-mono">{result.result_data.token_usage.total_tokens?.toLocaleString()}</span></div>
                              </div>
                            )}
                            {isSubtitle && subtitleText ? (
                              <div className="space-y-4">
                                <div className="rounded bg-slate-100 p-4 dark:bg-slate-800">
                                  <pre className="whitespace-pre-wrap text-sm font-mono">
                                    {subtitleText}
                                  </pre>
                                </div>
                                <details className="text-xs text-muted-foreground">
                                  <summary className="cursor-pointer hover:text-foreground">Show raw JSON</summary>
                                  <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-3 dark:bg-slate-900">
                                    {JSON.stringify(result.result_data, null, 2)}
                                  </pre>
                                </details>
                              </div>
                            ) : (
                              <pre className="overflow-x-auto rounded bg-slate-100 p-3 text-xs dark:bg-slate-800">
                                {JSON.stringify(result.result_data, null, 2)}
                              </pre>
                            )}
                          </AccordionContent>
                        </AccordionItem>
                      )
                    })}
                  </Accordion>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
