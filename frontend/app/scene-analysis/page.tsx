'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Video as VideoIcon, FileVideo, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { videoApi, sceneJobApi } from '@/lib/api-client'
import { SceneJob, SceneJobStatus, ContextItem } from '@/lib/types'
import { VideoPicker } from '@/components/video-picker'
import { SceneJobCard } from '@/components/scene/job-card'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function SceneAnalysisPage() {
  const [showPicker, setShowPicker] = useState(false)

  const { data: sceneJobs, isLoading, refetch } = useQuery<SceneJob[]>({
    queryKey: ['scene-jobs'],
    queryFn: () => sceneJobApi.listJobs(),
    refetchInterval: (query) => {
      // Auto-refresh if any scene job is being processed
      const activeStatuses = [
        SceneJobStatus.PENDING,
        SceneJobStatus.PROCESSING,
      ]
      const hasActiveJobs = query.state.data?.some(
        (job: SceneJob) => activeStatuses.includes(job.status)
      )
      return hasActiveJobs ? 3000 : false // 3 seconds
    },
  })

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => sceneJobApi.deleteJob(jobId),
    onSuccess: () => {
      refetch()
    },
  })

  const handleVideoSelect = async (
    videoId: string,
    isCompressed: boolean,
    gcsPath: string,
    chunkDuration: number,
    promptId: string,
    contextItems?: ContextItem[]
  ) => {
    // Start scene analysis for the selected (already compressed) video
    // The video is already compressed from /media workflow, we just need to chunk and analyze
    try {
      console.log('=== handleVideoSelect called ===')
      console.log('videoId:', videoId)
      console.log('gcsPath:', gcsPath)
      console.log('chunkDuration:', chunkDuration, 'type:', typeof chunkDuration)
      console.log('promptId:', promptId)
      console.log('contextItems:', contextItems)

      await videoApi.processVideo(videoId, {
        prompt_id: promptId,             // User-selected prompt (required)
        compressed_video_path: gcsPath, // GCS path from media job
        chunk_duration: chunkDuration,  // User-selected chunk duration
        chunk: chunkDuration > 0,       // Only chunk if duration > 0
        compress: false,                 // Already compressed in media workflow
        extract_audio: false,            // Already extracted in media workflow
        context_items: contextItems,     // Optional context files for analysis
      })
      setShowPicker(false)
      refetch()
    } catch (error) {
      console.error('Failed to start scene analysis:', error)
      // TODO: Show error toast
    }
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Scene Analysis</h1>
          <p className="text-muted-foreground mt-1">AI-Powered Scene Analysis with Gemini</p>
        </div>
        {!showPicker && (
          <Button onClick={() => setShowPicker(true)} size="lg">
            <FileVideo className="mr-2 h-4 w-4" />
            Start New Analysis
          </Button>
        )}
      </div>
        {showPicker ? (
          <div className="mx-auto max-w-4xl">
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle>Select Media for Analysis</CardTitle>
                    <CardDescription>
                      Choose compressed video or extracted audio from your processed library
                    </CardDescription>
                  </div>
                  <Button variant="outline" onClick={() => setShowPicker(false)}>
                    Cancel
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <VideoPicker
                  onSelect={handleVideoSelect}
                  onCancel={() => setShowPicker(false)}
                />
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Stats */}
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Jobs</CardDescription>
                  <CardTitle className="text-3xl">{sceneJobs?.length || 0}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Pending</CardDescription>
                  <CardTitle className="text-3xl text-yellow-600">
                    {sceneJobs?.filter((job) => job.status === SceneJobStatus.PENDING).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Processing</CardDescription>
                  <CardTitle className="text-3xl text-blue-600">
                    {sceneJobs?.filter((job) => job.status === SceneJobStatus.PROCESSING).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Completed</CardDescription>
                  <CardTitle className="text-3xl text-green-600">
                    {sceneJobs?.filter((job) => job.status === SceneJobStatus.COMPLETED).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Scene Jobs List */}
            {isLoading ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground">Loading scene jobs...</p>
                </CardContent>
              </Card>
            ) : sceneJobs && sceneJobs.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle>Scene Analysis Jobs</CardTitle>
                  <CardDescription>{sceneJobs.length} job(s) total</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {sceneJobs.map((job) => (
                      <SceneJobCard
                        key={job.job_id}
                        job={job}
                        onDelete={(jobId) => deleteJobMutation.mutate(jobId)}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <VideoIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-4 text-lg font-semibold">No scene jobs yet</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Pick a video to start scene analysis
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}
    </div>
  )
}
