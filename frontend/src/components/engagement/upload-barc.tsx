import { useRef, useState } from 'react'
import { Upload, FileSpreadsheet, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { engagementApi, uploadToGCS } from '@/lib/api-client'

interface UploadBarcProps {
  onUploaded: (gcsPath: string, filename: string) => void
  uploadedGcsPath?: string | null
  uploadedFilename?: string | null
  onClear?: () => void
}

export function UploadBarc({ onUploaded, uploadedGcsPath, uploadedFilename, onClear }: UploadBarcProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFile = async (file: File) => {
    setError(null)
    if (!file.name.toLowerCase().endsWith('.csv') && file.type !== 'text/csv' && file.type !== 'application/vnd.ms-excel') {
      setError('Please upload a CSV file')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('CSV file must be under 10MB')
      return
    }
    try {
      setIsUploading(true)
      const { signed_url, gcs_path } = await engagementApi.getBarcSignedUrl(
        file.name,
        file.type || 'text/csv'
      )
      await uploadToGCS(signed_url, file)
      onUploaded(gcs_path, file.name)
    } catch (e) {
      console.error(e)
      setError('Upload failed — please try again')
    } finally {
      setIsUploading(false)
    }
  }

  if (uploadedGcsPath) {
    return (
      <div className="flex items-center justify-between rounded-lg border bg-muted/40 p-3">
        <div className="flex items-center gap-2 text-sm">
          <FileSpreadsheet className="h-4 w-4 text-green-600" />
          <span className="font-medium">{uploadedFilename || 'BARC file uploaded'}</span>
        </div>
        {onClear && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => inputRef.current?.click()}
        disabled={isUploading}
      >
        <Upload className="mr-2 h-4 w-4" />
        {isUploading ? 'Uploading…' : 'Upload BARC CSV'}
      </Button>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <p className="text-xs text-muted-foreground">
        CSV with a time column (timestamp / time / seconds) and a score column
        (engagement / score / value / rating).
      </p>
    </div>
  )
}
