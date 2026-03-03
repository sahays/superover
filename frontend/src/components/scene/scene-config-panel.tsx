import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PromptSelector } from '@/components/prompts/prompt-selector'
import { ContextUploadSection } from './context-upload-section'
import type { Prompt } from '@/lib/types'

interface ContextFile {
  file: File
  description: string
}

interface SceneConfigPanelProps {
  selectedCount: number
  selectedPromptId: string | null
  onPromptChange: (promptId: string | null) => void
  selectedPrompt: Prompt | undefined
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
  selectedCount,
  selectedPromptId,
  onPromptChange,
  selectedPrompt,
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
        <CardTitle className="text-base">Configure Analysis</CardTitle>
        <CardDescription>
          Select a prompt for {selectedCount} file{selectedCount > 1 ? 's' : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
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
            ) : selectedCount > 1 ? (
              `Analyze ${selectedCount} Files`
            ) : (
              'Start Analysis'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
