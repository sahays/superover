import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { videoApi, sceneJobApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { useSceneExport } from '@/hooks/use-scene-export'
import { SceneVideoMetadataCard } from '@/components/scene/scene-video-metadata-card'
import { SceneJobInfoCard } from '@/components/scene/scene-job-info-card'
import { SceneManifestCard } from '@/components/scene/scene-manifest-card'
import { SceneResultsCard } from '@/components/scene/scene-results-card'

export default function SceneDetailPage() {
  const { id: jobId } = useParams<{ id: string }>()

  const { data: sceneJob, isLoading: isLoadingJob } = useQuery({
    queryKey: ['scene-job', jobId],
    queryFn: () => sceneJobApi.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'processing' ? 3000 : false
    },
  })

  const videoId = sceneJob?.video_id

  const { data: scene, isLoading: isLoadingVideo } = useQuery({
    queryKey: ['scene', videoId],
    queryFn: () => videoApi.getVideo(videoId!),
    enabled: !!videoId,
  })

  const isLoading = isLoadingJob || isLoadingVideo
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

  const totalTokens = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.total_tokens || 0), 0) || 0
  const totalCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.estimated_cost_usd || 0), 0) || 0
  const totalInputCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.input_cost_usd || 0), 0) || 0
  const totalOutputCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.output_cost_usd || 0), 0) || 0

  const { isSubtitleJob, downloadAsJSON, downloadAsCSV, downloadAsSRT } = useSceneExport({
    results,
    sceneJob,
    jobId,
    filename: scene?.filename,
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
        <div className="mb-6 flex items-center justify-between">
          <Link to="/scene-analysis">
            <Button variant="ghost">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Scene Analysis
            </Button>
          </Link>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-3">
            {/* Results first */}
            {results && results.length > 0 && (
              <SceneResultsCard
                results={results}
                isSubtitleJob={!!isSubtitleJob}
                downloadAsJSON={downloadAsJSON}
                downloadAsCSV={downloadAsCSV}
                downloadAsSRT={downloadAsSRT}
              />
            )}

            {/* Metadata in collapsible accordion */}
            <Accordion type="multiple" className="w-full">
              {sceneJob && (
                <AccordionItem value="job-details">
                  <AccordionTrigger>Job Details</AccordionTrigger>
                  <AccordionContent>
                    <SceneJobInfoCard
                      sceneJob={sceneJob}
                      totalCost={totalCost}
                      totalInputCost={totalInputCost}
                      totalOutputCost={totalOutputCost}
                      totalTokens={totalTokens}
                    />
                  </AccordionContent>
                </AccordionItem>
              )}

              <AccordionItem value="video-metadata">
                <AccordionTrigger>Video Metadata</AccordionTrigger>
                <AccordionContent>
                  <SceneVideoMetadataCard scene={scene} />
                </AccordionContent>
              </AccordionItem>

              {manifest && (
                <AccordionItem value="processing-info">
                  <AccordionTrigger>Processing Info</AccordionTrigger>
                  <AccordionContent>
                    <SceneManifestCard manifest={manifest} />
                  </AccordionContent>
                </AccordionItem>
              )}
            </Accordion>
          </div>
        </div>
      </div>
    </div>
  )
}
