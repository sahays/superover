import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Upload, X, CheckCircle, AlertCircle } from 'lucide-react'
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

interface UploadVideoProps {
  onComplete: () => void
  onCancel: () => void
}

export function UploadVideo({ onComplete, onCancel }: UploadVideoProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      // Step 1: Get signed URL
      setUploadProgress(10)
      const { signed_url, gcs_path } = await videoApi.getSignedUrl(
        file.name,
        file.type
      )

      // Step 2: Upload to GCS and extract duration in parallel
      setUploadProgress(30)
      const [, duration] = await Promise.all([
        uploadToGCS(signed_url, file),
        extractMediaDuration(file),
      ])
      setUploadProgress(70)

      // Step 3: Create video record
      const video = await videoApi.createVideo({
        filename: file.name,
        gcs_path,
        content_type: file.type,
        size_bytes: file.size,
        ...(duration ? { metadata: { duration } } : {}),
      })

      setUploadProgress(100)

      return video
    },
    onSuccess: () => {
      setTimeout(() => {
        onComplete()
      }, 1000)
    },
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
    }
  }

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile)
    }
  }

  return (
    <div className="space-y-6">
      {/* File Selection */}
      {!selectedFile && !uploadMutation.isPending && (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 p-12 transition hover:border-primary">
          <Upload className="h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-semibold">Upload Media</h3>
          <p className="mt-2 text-sm text-gray-500">
            Select a video or audio file (up to 500MB)
          </p>
          <label htmlFor="file-upload" className="mt-4">
            <Button type="button" onClick={() => document.getElementById('file-upload')?.click()}>
              Select File
            </Button>
          </label>
          <input
            id="file-upload"
            type="file"
            accept="video/*,audio/*"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
      )}

      {/* File Selected */}
      {selectedFile && !uploadMutation.isPending && !uploadMutation.isSuccess && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Upload className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-medium">{selectedFile.name}</p>
                <p className="text-sm text-gray-500">{formatBytes(selectedFile.size)}</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSelectedFile(null)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex gap-2">
            <Button onClick={handleUpload} className="flex-1">
              Upload and Process
            </Button>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Uploading */}
      {uploadMutation.isPending && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <div>
                <p className="font-medium">Uploading...</p>
                <p className="text-sm text-gray-500">{uploadProgress}%</p>
              </div>
            </div>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Success */}
      {uploadMutation.isSuccess && (
        <div className="flex items-center justify-center rounded-lg border border-green-200 bg-green-50 p-8">
          <div className="text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-green-600" />
            <h3 className="mt-4 text-lg font-semibold text-green-900">Upload Complete!</h3>
            <p className="mt-2 text-sm text-green-700">
              Media file uploaded successfully
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {uploadMutation.isError && (
        <div className="space-y-4">
          <div className="flex items-center justify-center rounded-lg border border-red-200 bg-red-50 p-8">
            <div className="text-center">
              <AlertCircle className="mx-auto h-12 w-12 text-red-600" />
              <h3 className="mt-4 text-lg font-semibold text-red-900">Upload Failed</h3>
              <p className="mt-2 text-sm text-red-700">
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : 'Unknown error'}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => {
                uploadMutation.reset()
                setSelectedFile(null)
              }}
              className="flex-1"
              variant="outline"
            >
              Try Again
            </Button>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
