import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Save, Loader2 } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { promptApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'
import { usePromptForm, type PromptFormData } from '@/hooks/use-prompt-form'
import { toast } from 'sonner'

export default function CreatePromptPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { formData, setFormData, formErrors, validateForm } = usePromptForm()

  const toApiPayload = (data: PromptFormData) => {
    const { response_schema_json, ...rest } = data
    const payload: Record<string, unknown> = { ...rest }
    if (data.response_type === 'structured_json' && response_schema_json) {
      payload.response_schema = JSON.parse(response_schema_json)
    } else if (data.response_type === 'free_text') {
      payload.response_schema = null
    }
    if (!data.response_type) {
      delete payload.response_type
      delete payload.response_schema
    }
    return payload
  }

  const createMutation = useMutation({
    mutationFn: (data: PromptFormData) => promptApi.createPrompt(toApiPayload(data) as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      toast.success('Prompt created')
      navigate('/prompts')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create prompt')
    },
  })

  const handleSubmit = () => {
    if (!validateForm()) return
    createMutation.mutate(formData)
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/prompts">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <h1 className="text-2xl font-bold font-heading">Create Prompt</h1>
        </div>
        <Button onClick={handleSubmit} disabled={createMutation.isPending}>
          {createMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Create
        </Button>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Name <span className="text-red-500">*</span></Label>
          <Input
            id="name"
            placeholder="e.g., Sports Highlights Analysis"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className={formErrors.name ? 'border-red-500' : ''}
          />
          {formErrors.name && <p className="text-sm text-red-500">{formErrors.name}</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="type">Type <span className="text-red-500">*</span></Label>
          <Select value={formData.type} onValueChange={(value) => setFormData({ ...formData, type: value })}>
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
            onChange={(e) => setFormData({ ...formData, prompt_text: e.target.value })}
            rows={12}
            className={`font-mono text-sm ${formErrors.prompt_text ? 'border-red-500' : ''}`}
          />
          {formErrors.prompt_text && <p className="text-sm text-red-500">{formErrors.prompt_text}</p>}
          <p className="text-xs text-muted-foreground">
            {formData.prompt_text.length.toLocaleString()} / 50,000 characters
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="response_type">Response Type</Label>
          <Select
            value={formData.response_type || 'structured_json'}
            onValueChange={(value) => setFormData({
              ...formData,
              response_type: value,
              response_schema_json: value !== 'structured_json' ? '' : formData.response_schema_json,
            })}
          >
            <SelectTrigger id="response_type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="structured_json">Structured JSON</SelectItem>
              <SelectItem value="free_text">Free Text</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {formData.response_type === 'structured_json' && (
          <div className="space-y-2">
            <Label htmlFor="response_schema_json">JSON Schema <span className="text-red-500">*</span></Label>
            <Textarea
              id="response_schema_json"
              placeholder='{"type": "object", "properties": {...}}'
              value={formData.response_schema_json || ''}
              onChange={(e) => setFormData({ ...formData, response_schema_json: e.target.value })}
              rows={8}
              className={`font-mono text-sm ${formErrors.response_schema_json ? 'border-red-500' : ''}`}
            />
            {formErrors.response_schema_json && (
              <p className="text-sm text-red-500">{formErrors.response_schema_json}</p>
            )}
          </div>
        )}

        <div className="space-y-3 rounded-lg border p-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="supports_context"
              checked={formData.supports_context}
              onCheckedChange={(checked) => setFormData({ ...formData, supports_context: checked as boolean })}
            />
            <Label htmlFor="supports_context" className="text-sm font-medium leading-none">
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
                onChange={(e) => setFormData({ ...formData, context_description: e.target.value })}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
