'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Video as VideoIcon, Upload, PlayCircle, AlertCircle } from 'lucide-react'
import { videoApi } from '@/lib/api-client'
import { Video, VideoStatus } from '@/lib/types'
import { UploadVideo } from '@/components/upload-video'
import { VideoList } from '@/components/video-list'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function HomePage() {
  const [showUpload, setShowUpload] = useState(false)

  const { data: videos, isLoading, error, refetch } = useQuery({
    queryKey: ['videos'],
    queryFn: () => videoApi.listVideos(),
    refetchInterval: (query) => {
      // Auto-refresh if any video is being processed
      const activeStatuses = [
        VideoStatus.EXTRACTING_METADATA,
        VideoStatus.EXTRACTING_AUDIO,
        VideoStatus.COMPRESSING,
        VideoStatus.CHUNKING,
        VideoStatus.ANALYZING,
      ]
      const hasActiveVideos = query.state.data?.some(
        (v: Video) => activeStatuses.includes(v.status)
      )
      return hasActiveVideos ? 3000 : false // 3 seconds
    },
  })

  const handleUploadComplete = () => {
    setShowUpload(false)
    refetch()
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Header */}
      <header className="border-b bg-white/50 backdrop-blur-sm dark:bg-slate-900/50">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <VideoIcon className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Super Over Alchemy</h1>
                <p className="text-sm text-muted-foreground">AI-Powered Video Analysis</p>
              </div>
            </div>
            <Button onClick={() => setShowUpload(true)} size="lg">
              <Upload className="mr-2 h-4 w-4" />
              Upload Video
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {showUpload ? (
          <div className="mx-auto max-w-2xl">
            <Card>
              <CardHeader>
                <CardTitle>Upload Video</CardTitle>
                <CardDescription>
                  Upload a video file to analyze with Gemini AI
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
                  <CardDescription>Total Videos</CardDescription>
                  <CardTitle className="text-3xl">{videos?.length || 0}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Processing</CardDescription>
                  <CardTitle className="text-3xl">
                    {videos?.filter((v: Video) =>
                      [
                        VideoStatus.EXTRACTING_METADATA,
                        VideoStatus.EXTRACTING_AUDIO,
                        VideoStatus.COMPRESSING,
                        VideoStatus.CHUNKING
                      ].includes(v.status)
                    ).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Analyzing</CardDescription>
                  <CardTitle className="text-3xl">
                    {videos?.filter((v: Video) => v.status === VideoStatus.ANALYZING).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Completed</CardDescription>
                  <CardTitle className="text-3xl">
                    {videos?.filter((v: Video) => v.status === VideoStatus.COMPLETED).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Video List */}
            {error ? (
              <Card>
                <CardContent className="flex items-center justify-center py-12">
                  <div className="text-center">
                    <AlertCircle className="mx-auto h-12 w-12 text-destructive" />
                    <h3 className="mt-4 text-lg font-semibold">Error loading videos</h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {error instanceof Error ? error.message : 'Unknown error'}
                    </p>
                    <Button onClick={() => refetch()} className="mt-4" variant="outline">
                      Try Again
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <VideoList videos={videos || []} isLoading={isLoading} onRefresh={refetch} />
            )}
          </div>
        )}
      </main>
    </div>
  )
}
