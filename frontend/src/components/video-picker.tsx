import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Video, ExternalLink, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { mediaApi, promptApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { type MediaJob, type Prompt, type ContextItem } from '@/lib/types'
import { useContextUpload } from '@/hooks/use-context-upload'
import { VideoCard } from '@/components/scene/video-card'
import { SceneConfigPanel } from '@/components/scene/scene-config-panel'

interface VideoPickerProps {
  onSelect: (
    videoId: string,
    isCompressed: boolean,
    gcsPath: string,
    chunkDuration: number,
    promptId: string,
    contextItems?: ContextItem[]
  ) => void
  onCancel: () => void
}

export interface VideoWithJobs {
  video_id: string
  filename: string
  gcs_path: string
  size_bytes?: number
  metadata?: {
    duration?: number
    video?: {
      width?: number
      height?: number
    }
  }
  jobs: MediaJob[]
  hasCompressed: boolean
  hasAudio: boolean
}

export interface SelectedVideoState {
  videoId: string
  isCompressed: boolean
  gcsPath: string
  jobId: string
  mediaType: 'video' | 'audio'
  compressedResolution?: string
  audioFormat?: string
  duration?: number
}

export function VideoPicker({ onSelect, onCancel }: VideoPickerProps) {
  const [selectedVideo, setSelectedVideo] = useState<SelectedVideoState | null>(null)
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null)

  const contextUpload = useContextUpload()

  const { data: allVideosWithJobs, isLoading: isLoadingVideos } = useQuery<VideoWithJobs[]>({
    queryKey: ['videos-with-jobs'],
    queryFn: mediaApi.getAllVideosWithJobs,
    refetchInterval: 5000,
  })

  const { data: selectedPrompt } = useQuery<Prompt>({
    queryKey: ['prompt', selectedPromptId],
    queryFn: () => promptApi.getPrompt(selectedPromptId!),
    enabled: !!selectedPromptId,
  })

  const videosWithJobs = allVideosWithJobs
  const isEmpty = !isLoadingVideos && (!videosWithJobs || videosWithJobs.length === 0)

  if (isLoadingVideos) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
            <p className="mt-4 text-sm text-muted-foreground">Loading videos...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (isEmpty) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Video className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-semibold">No videos uploaded</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Upload a video to get started with scene analysis
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              You can analyze original uploads directly, or process them first in the Media workflow
            </p>
            <Link to="/media">
              <Button className="mt-4">
                <ExternalLink className="mr-2 h-4 w-4" />
                Go to Media Processing
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        {videosWithJobs?.map((video) => (
          <VideoCard
            key={video.video_id}
            video={video}
            selectedVideo={selectedVideo}
            onSelectVideo={setSelectedVideo}
          />
        ))}
      </div>

      {selectedVideo && (
        <SceneConfigPanel
          selectedVideo={selectedVideo}
          selectedPromptId={selectedPromptId}
          onPromptChange={setSelectedPromptId}
          selectedPrompt={selectedPrompt}
          contextFiles={contextUpload.contextFiles}
          showContextUpload={contextUpload.showContextUpload}
          isUploadingContext={contextUpload.isUploadingContext}
          onShowContextUpload={() => contextUpload.setShowContextUpload(true)}
          onHideContextUpload={() => contextUpload.setShowContextUpload(false)}
          onContextFileUpload={contextUpload.handleFileUpload}
          onRemoveContextFile={contextUpload.removeContextFile}
          onCancel={onCancel}
          onSubmit={() => {
            if (selectedPromptId) {
              onSelect(
                selectedVideo.videoId,
                selectedVideo.isCompressed,
                selectedVideo.gcsPath,
                0,
                selectedPromptId,
                contextUpload.uploadedContextItems.length > 0
                  ? contextUpload.uploadedContextItems
                  : undefined
              )
            }
          }}
        />
      )}
    </div>
  )
}
