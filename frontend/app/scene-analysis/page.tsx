'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Video as VideoIcon, FileVideo, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { videoApi } from '@/lib/api-client'
import { Video, VideoStatus } from '@/lib/types'
import { VideoPicker } from '@/components/video-picker'
import { VideoList } from '@/components/video-list'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function SceneAnalysisPage() {
  const [showPicker, setShowPicker] = useState(false)

  const { data: scenes, isLoading, refetch } = useQuery({
    queryKey: ['scenes'],
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

  const handleVideoSelect = async (videoId: string, isCompressed: boolean, gcsPath: string, chunkDuration: number) => {
    // Start scene analysis for the selected (already compressed) video
    // The video is already compressed from /media workflow, we just need to chunk and analyze
    try {
      // Pass chunk duration to the processing endpoint
      // TODO: Update API to accept compressed video path and chunk duration
      await videoApi.processVideo(videoId, {
        compress: false, // Already compressed
        chunk: chunkDuration > 0, // Only chunk if duration > 0
        extract_audio: false, // Already extracted in media workflow
      })
      setShowPicker(false)
      refetch()
    } catch (error) {
      console.error('Failed to start scene analysis:', error)
      // TODO: Show error toast
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Header */}
      <header className="border-b bg-white/50 backdrop-blur-sm dark:bg-slate-900/50">
        <div className="container mx-auto max-w-6xl px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-600 text-white">
                <VideoIcon className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Scene Analysis</h1>
                <p className="text-sm text-muted-foreground">AI-Powered Scene Analysis with Gemini</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Home
                </Button>
              </Link>
              <Button onClick={() => setShowPicker(true)} size="lg">
                <FileVideo className="mr-2 h-4 w-4" />
                Pick Video
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto max-w-6xl px-4 py-8">
        {showPicker ? (
          <div className="mx-auto max-w-4xl">
            <Card>
              <CardHeader>
                <CardTitle>Pick Video for Scene Analysis</CardTitle>
                <CardDescription>
                  Select a video from your processed library for scene analysis with Gemini AI
                </CardDescription>
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
                  <CardDescription>Total Scenes</CardDescription>
                  <CardTitle className="text-3xl">{scenes?.length || 0}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Processing</CardDescription>
                  <CardTitle className="text-3xl">
                    {scenes?.filter((v: Video) =>
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
                    {scenes?.filter((v: Video) => v.status === VideoStatus.ANALYZING).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Completed</CardDescription>
                  <CardTitle className="text-3xl">
                    {scenes?.filter((v: Video) => v.status === VideoStatus.COMPLETED).length || 0}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Scene List */}
            <VideoList videos={scenes || []} isLoading={isLoading} onRefresh={refetch} />
          </div>
        )}
      </main>
    </div>
  )
}
