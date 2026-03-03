import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'
import type { PromptFormData } from '@/hooks/use-prompt-form'

interface PromptFormDialogProps {
  open: boolean
  isEditing: boolean
  formData: PromptFormData
  formErrors: Partial<PromptFormData>
  onFormChange: (data: PromptFormData) => void
  onSubmit: () => void
  onClose: () => void
  isSaving: boolean
}

export function PromptFormDialog({
  open,
  isEditing,
  formData,
  formErrors,
  onFormChange,
  onSubmit,
  onClose,
  isSaving,
}: PromptFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Prompt' : 'Create New Prompt'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the prompt name and text. Changes will apply to new jobs only.'
              : 'Create a new prompt for scene analysis. You can use this prompt when starting new analysis jobs.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name <span className="text-red-500">*</span></Label>
            <Input
              id="name"
              placeholder="e.g., Sports Highlights Analysis"
              value={formData.name}
              onChange={(e) => onFormChange({ ...formData, name: e.target.value })}
              className={formErrors.name ? 'border-red-500' : ''}
            />
            {formErrors.name && <p className="text-sm text-red-500">{formErrors.name}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="type">Type <span className="text-red-500">*</span></Label>
            <Select value={formData.type} onValueChange={(value) => onFormChange({ ...formData, type: value })}>
              <SelectTrigger id="type" className={formErrors.type ? 'border-red-500' : ''}>
                <SelectValue placeholder="Select type..." />
              </SelectTrigger>
              <SelectContent>
                {PROMPT_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {formErrors.type && <p className="text-sm text-red-500">{formErrors.type}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="prompt_text">Prompt Text <span className="text-red-500">*</span></Label>
            <Textarea
              id="prompt_text"
              placeholder="Enter the prompt for scene analysis..."
              value={formData.prompt_text}
              onChange={(e) => onFormChange({ ...formData, prompt_text: e.target.value })}
              rows={10}
              className={formErrors.prompt_text ? 'border-red-500' : ''}
            />
            {formErrors.prompt_text && <p className="text-sm text-red-500">{formErrors.prompt_text}</p>}
            <p className="text-xs text-muted-foreground">
              {formData.prompt_text.length.toLocaleString()} / 50,000 characters
            </p>
          </div>
          <div className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="supports_context"
                checked={formData.supports_context}
                onCheckedChange={(checked) => onFormChange({ ...formData, supports_context: checked as boolean })}
              />
              <Label htmlFor="supports_context" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Supports additional context files
              </Label>
            </div>
            {formData.supports_context && (
              <div className="space-y-2 pl-6">
                <Label htmlFor="context_description" className="text-sm">Context Description (Optional)</Label>
                <Input
                  id="context_description"
                  placeholder="e.g., Upload player statistics or team roster"
                  value={formData.context_description || ''}
                  onChange={(e) => onFormChange({ ...formData, context_description: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  Describe what type of context files users should upload for this prompt
                </p>
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={onSubmit} disabled={isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
