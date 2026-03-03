import { Upload, X, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatBytes } from '@/lib/utils'
import type { Prompt } from '@/lib/types'

interface ContextFile {
  file: File
  description: string
}

interface ContextUploadSectionProps {
  selectedPrompt: Prompt
  contextFiles: ContextFile[]
  showContextUpload: boolean
  isUploadingContext: boolean
  onShowUpload: () => void
  onHideUpload: () => void
  onFileUpload: (file: File) => void
  onRemoveFile: (index: number) => void
}

export function ContextUploadSection({
  selectedPrompt,
  contextFiles,
  showContextUpload,
  isUploadingContext,
  onShowUpload,
  onHideUpload,
  onFileUpload,
  onRemoveFile,
}: ContextUploadSectionProps) {
  return (
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
            onClick={onShowUpload}
          >
            <Upload className="mr-2 h-4 w-4" />
            Add Context
          </Button>
        )}
      </div>

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
                onClick={() => onRemoveFile(index)}
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
              onClick={onShowUpload}
            >
              <Upload className="mr-2 h-4 w-4" />
              Add Another File
            </Button>
          )}
        </div>
      )}

      {showContextUpload && (
        <div className="rounded-lg border p-4 space-y-3">
          <div className="space-y-2">
            <Label htmlFor="context-file" className="text-sm">Text File</Label>
            <Input
              id="context-file"
              type="file"
              accept=".txt,.md,.json"
              disabled={isUploadingContext}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) {
                  onFileUpload(file)
                  e.target.value = ''
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
              onClick={onHideUpload}
              disabled={isUploadingContext}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
