import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Video, FileVideo, CheckCircle, ExternalLink, Loader2, Music, Upload, X, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { mediaApi, promptApi, videoApi, uploadToGCS } from '@/lib/api-client'
import { v4 as uuidv4 } from 'uuid'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatBytes, formatDuration } from '@/lib/utils'
import { MediaJobStatus, type MediaJob, type Prompt, type ContextItem } from '@/lib/types'
import { PromptSelector } from '@/components/prompts/prompt-selector'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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

export function VideoPicker({ onSelect, onCancel }: VideoPickerProps) {
  const [selectedVideo, setSelectedVideo] = useState<{
    videoId: string
    isCompressed: boolean
    gcsPath: string
    jobId: string
    mediaType: 'video' | 'audio'
    compressedResolution?: string
    audioFormat?: string
    duration?: number
  } | null>(null)
  const [chunkDuration, setChunkDuration] = useState<number>(0) // Default: No chunking
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null)
  const [contextFiles, setContextFiles] = useState<Array<{
    file: File
    description: string
  }>>([])
  const [uploadedContextItems, setUploadedContextItems] = useState<ContextItem[]>([])
  const [showContextUpload, setShowContextUpload] = useState(false)
  const [isUploadingContext, setIsUploadingContext] = useState(false)

  // Fetch all videos with their jobs
  const { data: allVideosWithJobs, isLoading: isLoadingVideos } = useQuery<VideoWithJobs[]>({
    queryKey: ['videos-with-jobs'],
    queryFn: mediaApi.getAllVideosWithJobs,
    refetchInterval: 5000, // Refresh every 5 seconds for active jobs
  })

  // Fetch selected prompt details
  const { data: selectedPrompt } = useQuery<Prompt>({
    queryKey: ['prompt', selectedPromptId],
    queryFn: () => promptApi.getPrompt(selectedPromptId!),
    enabled: !!selectedPromptId,
  })

  // Filter to only show videos with completed media processing jobs (video or audio)
  const videosWithJobs = allVideosWithJobs?.filter(video =>
    video.jobs.some(job =>
      job.status === MediaJobStatus.COMPLETED &&
      (job.results?.compressed_video_path || job.results?.audio_path)
    )
  )

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
            <h3 className="mt-4 text-lg font-semibold">No processed media available</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              You need to upload and process videos in the Media workflow first
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Scene analysis can use compressed videos or extracted audio files from media processing
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
          <Card key={video.video_id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="line-clamp-1 text-base">{video.filename}</CardTitle>
              <CardDescription className="flex items-center gap-2">
                {video.size_bytes && formatBytes(video.size_bytes)}
                {video.metadata?.duration && (
                  <>
                    <span>•</span>
                    {formatDuration(video.metadata.duration)}
                  </>
                )}
                {video.metadata?.video?.width && video.metadata?.video?.height && (
                  <>
                    <span>•</span>
                    {video.metadata.video.width}×{video.metadata.video.height}
                  </>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {/* Processed Video and Audio Options */}
              {video.jobs
                .filter((job) =>
                  job.status === MediaJobStatus.COMPLETED &&
                  (job.results?.compressed_video_path || job.results?.audio_path)
                )
                .map((job) => (
                  <div key={job.job_id} className="space-y-2">
                    {/* Compressed Video Option */}
                    {job.results?.compressed_video_path && (
                      <Button
                        variant={
                          selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'video'
                            ? 'default'
                            : 'outline'
                        }
                        className="w-full justify-start"
                        onClick={() => {
                          setSelectedVideo({
                            videoId: video.video_id,
                            isCompressed: true,
                            gcsPath: job.results!.compressed_video_path!,
                            jobId: job.job_id,
                            mediaType: 'video',
                            compressedResolution: job.config.compress_resolution,
                            duration: job.results?.metadata?.duration || video.metadata?.duration,
                          })
                        }}
                      >
                        <FileVideo className="mr-2 h-4 w-4" />
                        <span className="flex-1 text-left">
                          {job.config.compress_resolution} Video
                          {job.results?.compression_ratio && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              ({job.results.compression_ratio.toFixed(1)}% smaller)
                            </span>
                          )}
                        </span>
                        {selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'video' && (
                          <CheckCircle className="h-4 w-4" />
                        )}
                      </Button>
                    )}

                    {/* Audio Option */}
                    {job.results?.audio_path && (
                      <Button
                        variant={
                          selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'audio'
                            ? 'default'
                            : 'outline'
                        }
                        className="w-full justify-start"
                        onClick={() => {
                          setSelectedVideo({
                            videoId: video.video_id,
                            isCompressed: false,
                            gcsPath: job.results!.audio_path!,
                            jobId: job.job_id,
                            mediaType: 'audio',
                            audioFormat: job.config.audio_format,
                            duration: job.results?.metadata?.duration || video.metadata?.duration,
                          })
                        }}
                      >
                        <Music className="mr-2 h-4 w-4" />
                        <span className="flex-1 text-left">
                          {job.config.audio_format?.toUpperCase() || 'Audio'} @ {job.config.audio_bitrate}
                          {job.results?.audio_size_bytes && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              ({formatBytes(job.results.audio_size_bytes)})
                            </span>
                          )}
                          {(job.results?.metadata?.duration || video.metadata?.duration) && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              • {formatDuration(job.results?.metadata?.duration || video.metadata?.duration)}
                            </span>
                          )}
                        </span>
                        {selectedVideo?.jobId === job.job_id && selectedVideo?.mediaType === 'audio' && (
                          <CheckCircle className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                  </div>
                ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedVideo && (
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
            </div>

            {/* Prompt Selector */}
            <PromptSelector
              value={selectedPromptId}
              onChange={setSelectedPromptId}
              required={true}
              error={!selectedPromptId ? 'Please select a prompt' : undefined}
            />

            {/* Context Upload Section - Progressive Disclosure */}
            {selectedPrompt?.supports_context && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-sm font-medium">Additional Context (Optional)</Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      {selectedPrompt.context_description || 'Upload additional context files to enhance analysis'}
                    </p>
                  </div>
                  {!showContextUpload && contextFiles.length === 0 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setShowContextUpload(true)}
                    >
                      <Upload className="mr-2 h-4 w-4" />
                      Add Context
                    </Button>
                  )}
                </div>

                {/* Context Files List */}
                {contextFiles.length > 0 && (
                  <div className="space-y-2">
                    {contextFiles.map((item, index) => (
                      <div key={index} className="flex items-start gap-2 rounded-lg border p-3">
                        <FileText className="h-4 w-4 mt-0.5 text-blue-600 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{item.file.name}</p>
                          <p className="text-xs text-muted-foreground">{formatBytes(item.file.size)}</p>
                          {item.description && (
                            <p className="text-xs text-muted-foreground mt-1 italic">{item.description}</p>
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setContextFiles(contextFiles.filter((_, i) => i !== index))
                            setUploadedContextItems(uploadedContextItems.filter((_, i) => i !== index))
                          }}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {contextFiles.length < (selectedPrompt.max_context_items || 5) && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setShowContextUpload(true)}
                      >
                        <Upload className="mr-2 h-4 w-4" />
                        Add Another File
                      </Button>
                    )}
                  </div>
                )}

                {/* Context Upload Form */}
                {showContextUpload && (
                  <div className="rounded-lg border p-4 space-y-3">
                    <div className="space-y-2">
                      <Label htmlFor="context-file" className="text-sm">Text File</Label>
                      <Input
                        id="context-file"
                        type="file"
                        accept=".txt,.md,.json"
                        disabled={isUploadingContext}
                        onChange={async (e) => {
                          const file = e.target.files?.[0]
                          if (file) {
                            // Validate file size (max 10MB)
                            if (file.size > 10 * 1024 * 1024) {
                              alert('File size must be less than 10MB')
                              return
                            }

                            try {
                              setIsUploadingContext(true)

                              // Get signed URL for upload
                              const { signed_url, gcs_path } = await videoApi.getContextSignedUrl(
                                file.name,
                                file.type || 'text/plain'
                              )

                              // Upload file to GCS
                              await uploadToGCS(signed_url, file)

                              // Determine file type based on extension
                              const fileExt = file.name.split('.').pop()?.toLowerCase()
                              const contextType = 'text' // Currently only supporting text files

                              // Create context item
                              const contextItem: ContextItem = {
                                context_id: uuidv4(),
                                type: contextType,
                                gcs_path,
                                filename: file.name,
                                description: '',
                                size_bytes: file.size,
                              }

                              // Add to uploaded items
                              setUploadedContextItems([...uploadedContextItems, contextItem])

                              // Add to local display list
                              setContextFiles([...contextFiles, { file, description: '' }])
                              setShowContextUpload(false)
                              e.target.value = '' // Reset input
                            } catch (error) {
                              console.error('Failed to upload context file:', error)
                              alert('Failed to upload context file. Please try again.')
                            } finally {
                              setIsUploadingContext(false)
                            }
                          }
                        }}
                      />
                      <p className="text-xs text-muted-foreground">
                        Supported formats: .txt, .md, .json (max 10MB)
                        {isUploadingContext && <span className="ml-2 text-blue-600">Uploading...</span>}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowContextUpload(false)}
                        disabled={isUploadingContext}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Chunk Duration */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Chunk Duration (seconds)
              </label>

              {/* Chunking Guidance */}
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                <p className="font-medium mb-1">Chunking splits your media into segments for analysis.</p>
                <p className="mb-1">Recommended:</p>
                <ul className="list-disc list-inside space-y-0.5 ml-2">
                  <li>Audio &lt; 5 hours: No chunking (default)</li>
                  <li>Video &lt; 1 hour: No chunking (default)</li>
                  <li>Longer files: Use chunking to stay within limits</li>
                </ul>
                <p className="mt-2 text-slate-600 dark:text-slate-400">
                  Note: No chunking gives you 4× better API quota usage and avoids timestamp ordering issues.
                </p>
              </div>

              <div className="flex items-center gap-4">
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={chunkDuration}
                  onChange={(e) => setChunkDuration(parseInt(e.target.value) || 0)}
                  className="flex h-10 w-24 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                />
                <div className="flex-1 space-y-1">
                  <p className="text-sm text-muted-foreground">
                    {chunkDuration === 0
                      ? `No chunking - analyze entire ${selectedVideo.mediaType} as one piece`
                      : `Split ${selectedVideo.mediaType} into ${chunkDuration}-second chunks for analysis`
                    }
                  </p>
                  {selectedVideo.duration && chunkDuration > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Estimated {Math.ceil(selectedVideo.duration / chunkDuration)} chunks
                    </p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setChunkDuration(0)}
                  >
                    No chunks (recommended)
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setChunkDuration(60)}
                  >
                    60s
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setChunkDuration(120)}
                  >
                    120s
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setChunkDuration(300)}
                  >
                    5 min
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setChunkDuration(600)}
                  >
                    10 min
                  </Button>
                </div>
            </div>

            <div className="flex justify-end gap-2 border-t pt-4">
              <Button variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button
                disabled={!selectedPromptId || isUploadingContext}
                onClick={() => {
                  if (selectedPromptId) {
                    onSelect(
                      selectedVideo.videoId,
                      selectedVideo.isCompressed,
                      selectedVideo.gcsPath,
                      chunkDuration,
                      selectedPromptId,
                      uploadedContextItems.length > 0 ? uploadedContextItems : undefined
                    )
                  }
                }}
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
      )}
    </div>
  )
}
