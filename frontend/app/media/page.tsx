'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Film, Upload, ArrowLeft, Video as VideoIcon, Settings } from 'lucide-react'
import Link from 'next/link'
import { videoApi, mediaApi } from '@/lib/api-client'
import { UploadVideo } from '@/components/upload-video'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { StartProcessing } from '@/components/media/start-processing'
import { JobCard } from '@/components/media/job-card'
import { formatBytes } from '@/lib/utils'

export default function MediaProcessingPage() {
  const [showUpload, setShowUpload] = useState(false)
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null)
  const [showProcessDialog, setShowProcessDialog] = useState(false)

  const { data: videos, isLoading: videosLoading, refetch: refetchVideos } = useQuery({
    queryKey: ['media-videos'],
    queryFn: () => mediaApi.listVideos(),
  })

  const { data: allMediaJobs, refetch: refetchJobs } = useQuery({
    queryKey: ['all-media-jobs'],
    queryFn: async () => {
      if (!videos || videos.length === 0) return []

      // Fetch jobs for all videos
      const jobsPromises = videos.map((v: any) =>
        mediaApi.listJobsForVideo(v.video_id).catch(() => [])
      )
      const jobsArrays = await Promise.all(jobsPromises)
      return jobsArrays.flat()
    },
    enabled: !!videos && videos.length > 0,
    refetchInterval: 5000, // Poll every 5 seconds
  })

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => mediaApi.deleteJob(jobId),
    onSuccess: () => {
      refetchJobs()
    },
  })

  const handleUploadComplete = () => {
    setShowUpload(false)
    refetchVideos()
  }

  const handleStartProcessing = (videoId: string) => {
    setSelectedVideoId(videoId)
    setShowProcessDialog(true)
  }

  const handleProcessingComplete = () => {
    setShowProcessDialog(false)
    setSelectedVideoId(null)
    refetchJobs()
  }

  // Group jobs by status
  const pendingJobs = allMediaJobs?.filter(j => j.status === 'pending') || []
  const processingJobs = allMediaJobs?.filter(j => j.status === 'processing') || []
  const completedJobs = allMediaJobs?.filter(j => j.status === 'completed') || []
  const failedJobs = allMediaJobs?.filter(j => j.status === 'failed') || []

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Media Processing</h1>
          <p className="text-muted-foreground mt-1">Video Compression & Audio Extraction</p>
        </div>
        <Button onClick={() => setShowUpload(true)} size="lg">
          <Upload className="mr-2 h-4 w-4" />
          Upload Video
        </Button>
      </div>
        {showUpload ? (
          <div className="mx-auto max-w-2xl">
            <Card>
              <CardHeader>
                <CardTitle>Upload Video for Processing</CardTitle>
                <CardDescription>
                  Upload a video file to compress and extract audio
                </CardDescription>
              </CardHeader>
              <CardContent>
                <UploadVideo
                  onComplete={handleUploadComplete}
                  onCancel={() => setShowUpload(false)}
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
                  <CardTitle className="text-3xl">{allMediaJobs?.length || 0}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Processing</CardDescription>
                  <CardTitle className="text-3xl text-yellow-600">
                    {processingJobs.length + pendingJobs.length}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Completed</CardDescription>
                  <CardTitle className="text-3xl text-green-600">
                    {completedJobs.length}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Failed</CardDescription>
                  <CardTitle className="text-3xl text-red-600">
                    {failedJobs.length}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Videos Available for Processing */}
            <Card>
              <CardHeader>
                <CardTitle>Videos</CardTitle>
                <CardDescription>Select a video to start media processing</CardDescription>
              </CardHeader>
              <CardContent>
                {videosLoading ? (
                  <div className="text-center py-8 text-muted-foreground">
                    Loading videos...
                  </div>
                ) : videos && videos.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {videos.map((video: any) => (
                      <Card key={video.video_id} className="relative">
                        <CardHeader>
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <CardTitle className="text-base line-clamp-1">
                                {video.filename}
                              </CardTitle>
                              <CardDescription className="text-xs">
                                {video.size_bytes ? formatBytes(video.size_bytes) : 'Size unknown'}
                              </CardDescription>
                            </div>
                            <VideoIcon className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                          </div>
                        </CardHeader>
                        <CardContent>
                          <Button
                            className="w-full"
                            size="sm"
                            onClick={() => handleStartProcessing(video.video_id)}
                          >
                            <Settings className="mr-2 h-4 w-4" />
                            Process Video
                          </Button>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No videos uploaded yet. Upload a video to get started.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Processing Jobs */}
            {allMediaJobs && allMediaJobs.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Processing Jobs</CardTitle>
                  <CardDescription>{allMediaJobs.length} job(s) total</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {allMediaJobs.map((job: any) => (
                      <JobCard
                        key={job.job_id}
                        job={job}
                        onDelete={(jobId) => deleteJobMutation.mutate(jobId)}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

      {/* Processing Dialog */}
      <Dialog open={showProcessDialog} onOpenChange={setShowProcessDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Configure Media Processing</DialogTitle>
            <DialogDescription>
              Set compression resolution, audio format, and other options
            </DialogDescription>
          </DialogHeader>
          {selectedVideoId && (
            <StartProcessing
              videoId={selectedVideoId}
              onSuccess={handleProcessingComplete}
              onCancel={() => {
                setShowProcessDialog(false)
                setSelectedVideoId(null)
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
