import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { promptApi } from '@/lib/api-client'
import { Prompt } from '@/lib/types'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertCircle, FileText } from 'lucide-react'

interface PromptSelectorProps {
  value: string | null
  onChange: (promptId: string) => void
  required?: boolean
  error?: string
}

export function PromptSelector({ value, onChange, required = true, error }: PromptSelectorProps) {
  const { data: prompts, isLoading, error: fetchError } = useQuery<Prompt[]>({
    queryKey: ['prompts'],
    queryFn: () => promptApi.listPrompts(),
  })

  // Auto-select first prompt if none selected and prompts are loaded
  useEffect(() => {
    if (!value && prompts && prompts.length > 0 && !isLoading) {
      onChange(prompts[0].prompt_id)
    }
  }, [prompts, value, onChange, isLoading])

  if (fetchError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load prompts. Please refresh the page.
        </AlertDescription>
      </Alert>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Label htmlFor="prompt-select">
          Analysis Prompt {required && <span className="text-red-500">*</span>}
        </Label>
        <Select disabled>
          <SelectTrigger id="prompt-select">
            <SelectValue placeholder="Loading prompts..." />
          </SelectTrigger>
        </Select>
      </div>
    )
  }

  if (!prompts || prompts.length === 0) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          No prompts available. Please create a prompt first.
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-2">
      <Label htmlFor="prompt-select">
        Analysis Prompt {required && <span className="text-red-500">*</span>}
      </Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger
          id="prompt-select"
          className={error ? 'border-red-500' : ''}
        >
          <SelectValue placeholder="Select a prompt...">
            {value && prompts.find(p => p.prompt_id === value)?.name}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {prompts.map((prompt) => (
            <SelectItem key={prompt.prompt_id} value={prompt.prompt_id}>
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span>{prompt.name}</span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
      {value && prompts.find(p => p.prompt_id === value) && (
        <p className="text-xs text-muted-foreground line-clamp-2">
          {prompts.find(p => p.prompt_id === value)?.prompt_text}
        </p>
      )}
    </div>
  )
}
