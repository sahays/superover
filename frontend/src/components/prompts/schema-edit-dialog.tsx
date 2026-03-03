import { Loader2, X } from 'lucide-react'
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
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'

interface SchemaEditDialogProps {
  editingCategory: string | null
  schemaText: string
  onSchemaTextChange: (text: string) => void
  schemaError: string | null
  onSchemaErrorClear: () => void
  onSave: () => void
  onClear: () => void
  onClose: () => void
  isSaving: boolean
}

export function SchemaEditDialog({
  editingCategory,
  schemaText,
  onSchemaTextChange,
  schemaError,
  onSchemaErrorClear,
  onSave,
  onClear,
  onClose,
  isSaving,
}: SchemaEditDialogProps) {
  return (
    <Dialog open={editingCategory !== null} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Edit Response Schema</DialogTitle>
          <DialogDescription>
            Define the JSON response schema for <strong>{PROMPT_TYPE_OPTIONS.find(o => o.value === editingCategory)?.label || editingCategory}</strong> prompts.
            Leave empty or clear to use free text (no structured output).
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Category</Label>
            <Input value={editingCategory || ''} disabled />
          </div>
          <div className="space-y-2">
            <Label htmlFor="schema_json">JSON Schema</Label>
            <Textarea
              id="schema_json"
              placeholder='{"type": "object", "properties": { ... }}'
              value={schemaText}
              onChange={(e) => {
                onSchemaTextChange(e.target.value)
                onSchemaErrorClear()
              }}
              rows={14}
              className={`font-mono text-sm ${schemaError ? 'border-red-500' : ''}`}
            />
            {schemaError && <p className="text-sm text-red-500">{schemaError}</p>}
            <p className="text-xs text-muted-foreground">
              Paste a JSON schema object. Gemini will return responses matching this structure.
            </p>
          </div>
        </div>
        <DialogFooter className="flex justify-between sm:justify-between">
          <Button variant="destructive" size="sm" onClick={onClear} disabled={isSaving}>
            <X className="mr-2 h-4 w-4" />
            Clear Schema
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={onSave} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Schema
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
