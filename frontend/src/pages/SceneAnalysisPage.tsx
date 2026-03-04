import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Video as VideoIcon, FileVideo } from 'lucide-react'
import { videoApi, sceneJobApi } from '@/lib/api-client'
import { SceneJob, SceneJobStatus, ContextItem } from '@/lib/types'
import type { SelectedVideoState } from '@/components/video-picker'
import { VideoPicker } from '@/components/video-picker'
import { SceneJobCard } from '@/components/scene/job-card'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export default function SceneAnalysisPage() {
  const [showPicker, setShowPicker] = useState(false)
  const [promptTypeFilter, setPromptTypeFilter] = useState('all')
  const [videoFilenames, setVideoFilenames] = useState<Record<string, string>>({})

  const { data: sceneJobs, isLoading, refetch } = useQuery<SceneJob[]>({
    queryKey: ['scene-jobs'],
    queryFn: () => sceneJobApi.listJobs(),
    refetchInterval: (query) => {
      const activeStatuses = [
        SceneJobStatus.PENDING,
        SceneJobStatus.PROCESSING,
      ]
      const hasActiveJobs = query.state.data?.some(
        (job: SceneJob) => activeStatuses.includes(job.status)
      )
      return hasActiveJobs ? 3000 : false
    },
  })

  // Batch-fetch video filenames for all jobs
  useEffect(() => {
    if (!sceneJobs) return

    const uniqueVideoIds = [...new Set(sceneJobs.map((j) => j.video_id))]
    const missingIds = uniqueVideoIds.filter((id) => !(id in videoFilenames))

    if (missingIds.length === 0) return

    Promise.all(
      missingIds.map((id) =>
        videoApi.getVideo(id).then((v) => ({ id, filename: v.filename as string })).catch(() => null)
      )
    ).then((results) => {
      const newMap: Record<string, string> = {}
      for (const r of results) {
        if (r) newMap[r.id] = r.filename
      }
      if (Object.keys(newMap).length > 0) {
        setVideoFilenames((prev) => ({ ...prev, ...newMap }))
      }
    })
  }, [sceneJobs])

  // Extract unique prompt types for the filter dropdown
  const promptTypes = useMemo(() => {
    if (!sceneJobs) return []
    const types = new Set(sceneJobs.map((j) => j.prompt_type || 'custom'))
    return [...types].sort()
  }, [sceneJobs])

  // Filter jobs by selected prompt type (exclude archived by default)
  const filteredJobs = useMemo(() => {
    if (!sceneJobs) return []
    return sceneJobs.filter((job) => {
      if (job.status === SceneJobStatus.ARCHIVED) return false
      if (promptTypeFilter === 'all') return true
      return (job.prompt_type || 'custom') === promptTypeFilter
    })
  }, [sceneJobs, promptTypeFilter])

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => sceneJobApi.deleteJob(jobId),
    onSuccess: () => {
      refetch()
    },
  })

  const archiveJobMutation = useMutation({
    mutationFn: (jobId: string) => sceneJobApi.archiveJob(jobId),
    onSuccess: () => {
      toast.success('Job archived')
      refetch()
    },
    onError: () => {
      toast.error('Failed to archive job')
    },
  })

  const handleVideoSelect = async (
    selections: SelectedVideoState[],
    promptId: string,
    contextItems?: ContextItem[]
  ) => {
    setShowPicker(false)
    let queued = 0
    let failed = 0

    for (const sel of selections) {
      try {
        await videoApi.processVideo(sel.videoId, {
          prompt_id: promptId,
          compressed_video_path: sel.isCompressed ? sel.gcsPath : undefined,
          chunk_duration: 0,
          chunk: false,
          compress: false,
          extract_audio: false,
          context_items: contextItems,
        })
        queued++
      } catch (error) {
        failed++
        console.error(`Failed to queue analysis for ${sel.videoId}:`, error)
      }
    }

    refetch()
    if (queued > 0) {
      toast.success(`Queued ${queued} analysis job${queued > 1 ? 's' : ''}`)
    }
    if (failed > 0) {
      toast.error(`Failed to queue ${failed} job${failed > 1 ? 's' : ''}`)
    }
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold font-heading">Scene Analysis</h1>
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
                      Choose an original upload, compressed video, or extracted audio
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
                  <CardTitle className="text-3xl font-mono">{filteredJobs.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Pending</CardDescription>
                  <CardTitle className="text-3xl font-mono text-yellow-600">
                    {filteredJobs.filter((job) => job.status === SceneJobStatus.PENDING).length}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Processing</CardDescription>
                  <CardTitle className="text-3xl font-mono text-blue-600">
                    {filteredJobs.filter((job) => job.status === SceneJobStatus.PROCESSING).length}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Completed</CardDescription>
                  <CardTitle className="text-3xl font-mono text-green-600">
                    {filteredJobs.filter((job) => job.status === SceneJobStatus.COMPLETED).length}
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
            ) : filteredJobs.length > 0 ? (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Scene Analysis Jobs</CardTitle>
                      <CardDescription>{filteredJobs.length} job(s) total</CardDescription>
                    </div>
                    {promptTypes.length > 1 && (
                      <Select value={promptTypeFilter} onValueChange={setPromptTypeFilter}>
                        <SelectTrigger className="w-[180px]">
                          <SelectValue placeholder="Filter by type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Types</SelectItem>
                          {promptTypes.map((type) => (
                            <SelectItem key={type} value={type}>
                              {type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {filteredJobs.map((job) => (
                      <SceneJobCard
                        key={job.job_id}
                        job={job}
                        videoFilename={videoFilenames[job.video_id]}
                        onDelete={(jobId) => deleteJobMutation.mutate(jobId)}
                        onArchive={(jobId) => archiveJobMutation.mutate(jobId)}
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
