import { useState, useCallback } from 'react'
import { Upload, X, CheckCircle, AlertCircle, FileVideo } from 'lucide-react'
import { videoApi, uploadToGCS } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { formatBytes } from '@/lib/utils'

function extractMediaDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const isAudio = file.type.startsWith('audio/')
    const el = document.createElement(isAudio ? 'audio' : 'video') as HTMLMediaElement
    el.preload = 'metadata'
    el.onloadedmetadata = () => {
      const duration = isFinite(el.duration) ? el.duration : null
      URL.revokeObjectURL(url)
      resolve(duration)
    }
    el.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(null)
    }
    el.src = url
  })
}

type FileStatus = 'pending' | 'uploading' | 'done' | 'error'

interface TrackedFile {
  file: File
  status: FileStatus
  progress: number
  error?: string
}

interface UploadVideoProps {
  onComplete: () => void
  onCancel: () => void
}

export function UploadVideo({ onComplete, onCancel }: UploadVideoProps) {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [allDone, setAllDone] = useState(false)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files
    if (!selected || selected.length === 0) return
    const tracked: TrackedFile[] = Array.from(selected).map((file) => ({
      file,
      status: 'pending' as FileStatus,
      progress: 0,
    }))
    setFiles((prev) => [...prev, ...tracked])
  }

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const uploadSingleFile = useCallback(
    async (
      tracked: TrackedFile,
      index: number,
      updateFile: (index: number, patch: Partial<TrackedFile>) => void
    ) => {
      const { file } = tracked
      try {
        updateFile(index, { status: 'uploading', progress: 10 })

        const { signed_url, gcs_path } = await videoApi.getSignedUrl(
          file.name,
          file.type
        )
        updateFile(index, { progress: 30 })

        const [, duration] = await Promise.all([
          uploadToGCS(signed_url, file),
          extractMediaDuration(file),
        ])
        updateFile(index, { progress: 70 })

        await videoApi.createVideo({
          filename: file.name,
          gcs_path,
          content_type: file.type,
          size_bytes: file.size,
          ...(duration ? { metadata: { duration } } : {}),
        })

        updateFile(index, { status: 'done', progress: 100 })
      } catch (err) {
        updateFile(index, {
          status: 'error',
          error: err instanceof Error ? err.message : 'Upload failed',
        })
      }
    },
    []
  )

  const handleUpload = useCallback(async () => {
    setUploading(true)

    const updateFile = (index: number, patch: Partial<TrackedFile>) => {
      setFiles((prev) =>
        prev.map((f, i) => (i === index ? { ...f, ...patch } : f))
      )
    }

    // Upload all files concurrently (max 3 at a time)
    const concurrency = 3
    const queue = files.map((f, i) => i).filter((i) => files[i].status === 'pending')

    const runBatch = async (indices: number[]) => {
      await Promise.all(
        indices.map((i) => uploadSingleFile(files[i], i, updateFile))
      )
    }

    for (let i = 0; i < queue.length; i += concurrency) {
      const batch = queue.slice(i, i + concurrency)
      await runBatch(batch)
    }

    setUploading(false)
    setAllDone(true)
    setTimeout(() => onComplete(), 1500)
  }, [files, uploadSingleFile, onComplete])

  const hasFiles = files.length > 0
  const pendingCount = files.filter((f) => f.status === 'pending').length

  return (
    <div className="space-y-6">
      {/* File Selection Area */}
      {!uploading && !allDone && (
        <>
          <div
            className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 p-8 transition hover:border-primary cursor-pointer"
            onClick={() => document.getElementById('file-upload')?.click()}
          >
            <Upload className="h-10 w-10 text-gray-400" />
            <h3 className="mt-3 text-lg font-semibold font-heading">Upload Media</h3>
            <p className="mt-1 text-sm text-gray-500">
              Select one or more video/audio files (up to 500MB each)
            </p>
            <input
              id="file-upload"
              type="file"
              accept="video/*,audio/*"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>

          {/* Selected Files List */}
          {hasFiles && (
            <div className="space-y-2">
              <p className="text-sm font-medium">
                {files.length} file{files.length > 1 ? 's' : ''} selected
              </p>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {files.map((tracked, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileVideo className="h-5 w-5 text-muted-foreground shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">
                          {tracked.file.name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatBytes(tracked.file.size)}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={() => removeFile(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 pt-2">
                <Button onClick={handleUpload} className="flex-1" disabled={pendingCount === 0}>
                  Upload {pendingCount} File{pendingCount > 1 ? 's' : ''}
                </Button>
                <Button variant="outline" onClick={onCancel}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Uploading Progress */}
      {uploading && (
        <div className="space-y-3">
          <p className="text-sm font-medium">Uploading files...</p>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {files.map((tracked, index) => (
              <div key={index} className="rounded-lg border p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium truncate">{tracked.file.name}</p>
                  {tracked.status === 'done' && (
                    <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
                  )}
                  {tracked.status === 'error' && (
                    <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />
                  )}
                  {tracked.status === 'uploading' && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      <span className="font-mono">{tracked.progress}%</span>
                    </span>
                  )}
                </div>
                {(tracked.status === 'uploading' || tracked.status === 'done') && (
                  <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={`h-full transition-all duration-300 ${
                        tracked.status === 'done' ? 'bg-green-600' : 'bg-primary'
                      }`}
                      style={{ width: `${tracked.progress}%` }}
                    />
                  </div>
                )}
                {tracked.status === 'error' && tracked.error && (
                  <p className="text-xs text-red-600">{tracked.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Done */}
      {allDone && (
        <div className="flex items-center justify-center rounded-lg border border-green-200 bg-green-50 p-8">
          <div className="text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-green-600" />
            <h3 className="mt-4 text-lg font-semibold text-green-900">
              Upload Complete!
            </h3>
            <p className="mt-2 text-sm text-green-700">
              {files.filter((f) => f.status === 'done').length} of {files.length} file
              {files.length > 1 ? 's' : ''} uploaded successfully
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
