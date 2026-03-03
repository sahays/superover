import { Edit2, Trash2, Paperclip } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'
import type { Prompt } from '@/lib/types'

interface PromptCardProps {
  prompt: Prompt
  onEdit: (prompt: Prompt) => void
  onDelete: (prompt: Prompt) => void
  isDeleting: boolean
}

export function PromptCard({ prompt, onEdit, onDelete, isDeleting }: PromptCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CardTitle className="line-clamp-1">{prompt.name}</CardTitle>
              {prompt.supports_context && (
                <span title="Supports context files">
                  <Paperclip className="h-4 w-4 text-blue-600" aria-label="Supports context files" />
                </span>
              )}
            </div>
            <CardDescription className="mt-1">
              {PROMPT_TYPE_OPTIONS.find(opt => opt.value === prompt.type)?.label || prompt.type}
              {' • '}
              {prompt.jobs_count || 0} job(s)
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1">
        <p className="text-sm text-muted-foreground line-clamp-3">
          {prompt.prompt_text}
        </p>
        {prompt.supports_context && prompt.context_description && (
          <p className="mt-2 text-xs text-blue-600 italic">
            Context: {prompt.context_description}
          </p>
        )}
      </CardContent>
      <CardContent className="flex justify-end gap-2 border-t pt-4">
        <Button variant="outline" size="sm" onClick={() => onEdit(prompt)}>
          <Edit2 className="mr-2 h-4 w-4" />
          Edit
        </Button>
        <Button variant="outline" size="sm" onClick={() => onDelete(prompt)} disabled={isDeleting}>
          <Trash2 className="mr-2 h-4 w-4" />
          Delete
        </Button>
      </CardContent>
    </Card>
  )
}
