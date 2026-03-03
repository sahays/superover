import { Upload, FileVideo, Music, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PromptSelector } from '@/components/prompts/prompt-selector'
import { ContextUploadSection } from './context-upload-section'
import { ChunkDurationSelector } from './chunk-duration-selector'
import type { Prompt } from '@/lib/types'
import type { SelectedVideoState } from '@/components/video-picker'

interface ContextFile {
  file: File
  description: string
}

interface SceneConfigPanelProps {
  selectedVideo: SelectedVideoState
  selectedPromptId: string | null
  onPromptChange: (promptId: string | null) => void
  selectedPrompt: Prompt | undefined
  chunkDuration: number
  onChunkDurationChange: (duration: number) => void
  contextFiles: ContextFile[]
  showContextUpload: boolean
  isUploadingContext: boolean
  onShowContextUpload: () => void
  onHideContextUpload: () => void
  onContextFileUpload: (file: File) => void
  onRemoveContextFile: (index: number) => void
  onCancel: () => void
  onSubmit: () => void
}

export function SceneConfigPanel({
  selectedVideo,
  selectedPromptId,
  onPromptChange,
  selectedPrompt,
  chunkDuration,
  onChunkDurationChange,
  contextFiles,
  showContextUpload,
  isUploadingContext,
  onShowContextUpload,
  onHideContextUpload,
  onContextFileUpload,
  onRemoveContextFile,
  onCancel,
  onSubmit,
}: SceneConfigPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Configure Scene Analysis</CardTitle>
        <CardDescription>
          Select prompt and set chunk duration for {selectedVideo.mediaType} analysis
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Media Type Info */}
        <div className="rounded-lg bg-blue-50 p-3 text-sm">
          <div className="flex items-center gap-2">
            {selectedVideo.mediaType === 'audio' ? (
              <>
                <Music className="h-4 w-4 text-blue-600" />
                <span className="font-medium text-blue-900">Audio file selected</span>
              </>
            ) : selectedVideo.jobId === '' ? (
              <>
                <Upload className="h-4 w-4 text-blue-600" />
                <span className="font-medium text-blue-900">Original video selected</span>
              </>
            ) : (
              <>
                <FileVideo className="h-4 w-4 text-blue-600" />
                <span className="font-medium text-blue-900">
                  {selectedVideo.compressedResolution} video selected
                </span>
              </>
            )}
          </div>
          {selectedVideo.mediaType === 'audio' && (
            <p className="mt-1 text-xs text-blue-700">
              Audio-only analysis is ideal for subtitling, transcription, and voice analysis tasks.
              Use chunking for long audio files to avoid hitting token limits.
            </p>
          )}
          {selectedVideo.jobId === '' && (
            <p className="mt-1 text-xs text-blue-700">
              Analyzing the original uploaded file. For smaller file sizes, process the video in the Media workflow first.
            </p>
          )}
        </div>

        <PromptSelector
          value={selectedPromptId}
          onChange={onPromptChange}
          required={true}
          error={!selectedPromptId ? 'Please select a prompt' : undefined}
        />

        {selectedPrompt?.supports_context && (
          <ContextUploadSection
            selectedPrompt={selectedPrompt}
            contextFiles={contextFiles}
            showContextUpload={showContextUpload}
            isUploadingContext={isUploadingContext}
            onShowUpload={onShowContextUpload}
            onHideUpload={onHideContextUpload}
            onFileUpload={onContextFileUpload}
            onRemoveFile={onRemoveContextFile}
          />
        )}

        <ChunkDurationSelector
          chunkDuration={chunkDuration}
          onChunkDurationChange={onChunkDurationChange}
          mediaType={selectedVideo.mediaType}
          mediaDuration={selectedVideo.duration}
        />

        <div className="flex justify-end gap-2 border-t pt-4">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            disabled={!selectedPromptId || isUploadingContext}
            onClick={onSubmit}
          >
            {isUploadingContext ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              selectedVideo.mediaType === 'audio' ? 'Start Audio Analysis' : 'Start Scene Analysis'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
