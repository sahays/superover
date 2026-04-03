import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { promptApi } from '@/lib/api-client'
import { useAuthStore } from '@/store/useAuthStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'
import { useState, useEffect } from 'react'
import { toast } from 'sonner'

export default function EditPromptPage() {
  const navigate = useNavigate()
  const { promptId } = useParams<{ promptId: string }>()
  const queryClient = useQueryClient()
  const { isMaster } = useAuthStore()

  const [promptText, setPromptText] = useState('')
  const [responseType, setResponseType] = useState<string>('')
  const [schemaJson, setSchemaJson] = useState('')

  const { data: prompt, isLoading } = useQuery<any>({
    queryKey: ['prompt', promptId],
    queryFn: () => promptApi.getPrompt(promptId!),
    enabled: !!promptId && promptId !== 'new',
  })

  useEffect(() => {
    if (prompt) {
      setPromptText(prompt.prompt_text)
      setResponseType(prompt.response_type || '')
      setSchemaJson(prompt.response_schema ? JSON.stringify(prompt.response_schema, null, 2) : '')
    }
  }, [prompt])

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      promptApi.updatePrompt(promptId!, payload),
    onSuccess: () => {
      toast.success('Prompt updated')
      queryClient.invalidateQueries({ queryKey: ['prompt', promptId] })
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      navigate('/prompts')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || `Failed to update prompt: ${error.message}`)
    },
  })

  const handleSave = () => {
    const payload: Record<string, unknown> = { prompt_text: promptText }
    if (responseType) {
      payload.response_type = responseType
      if (responseType === 'structured_json' && schemaJson.trim()) {
        try {
          payload.response_schema = JSON.parse(schemaJson)
        } catch {
          toast.error('Invalid JSON schema')
          return
        }
      } else if (responseType === 'free_text') {
        payload.response_schema = null
      }
    }
    updateMutation.mutate(payload)
  }

  if (isLoading) {
    return (
      <div className="container mx-auto max-w-3xl px-4 py-8 flex justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!prompt) {
    return (
      <div className="container mx-auto max-w-3xl px-4 py-8 text-center">
        <p className="text-muted-foreground">Prompt not found</p>
        <Link to="/prompts">
          <Button className="mt-4" variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Prompts
          </Button>
        </Link>
      </div>
    )
  }

  const typeLabel = PROMPT_TYPE_OPTIONS.find(o => o.value === prompt.type)?.label || prompt.type

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
          <div>
            <h1 className="text-2xl font-bold font-heading">{isMaster ? 'Edit Prompt' : 'View Prompt'}</h1>
            <p className="text-sm text-muted-foreground">{prompt.name} &middot; {typeLabel}</p>
          </div>
        </div>
        {isMaster && (
          <Button onClick={handleSave} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Changes
          </Button>
        )}
      </div>

      {/* Prompt Text */}
      <div className="space-y-2">
        <Label>Prompt Text</Label>
        <Textarea
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          className="min-h-[400px] font-mono text-sm"
          placeholder="Enter the Gemini prompt text here..."
          readOnly={!isMaster}
        />
        <p className="text-xs text-muted-foreground">
          {promptText.length.toLocaleString()} / 50,000 characters
        </p>
      </div>

      {/* Response Type & Schema */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Response Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Response Type</Label>
            {isMaster ? (
              <Select
                value={responseType || '_default'}
                onValueChange={(v) => {
                  setResponseType(v === '_default' ? '' : v)
                  if (v !== 'structured_json') setSchemaJson('')
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_default">Default (category schema)</SelectItem>
                  <SelectItem value="structured_json">Structured JSON</SelectItem>
                  <SelectItem value="free_text">Free Text</SelectItem>
                </SelectContent>
              </Select>
            ) : (
              <Input
                value={responseType === 'structured_json' ? 'Structured JSON' : responseType === 'free_text' ? 'Free Text' : 'Default (category schema)'}
                readOnly
                className="bg-muted"
              />
            )}
          </div>

          {(responseType === 'structured_json' || (!isMaster && schemaJson)) && (
            <div className="space-y-2">
              <Label>JSON Schema</Label>
              <Textarea
                value={schemaJson}
                onChange={(e) => setSchemaJson(e.target.value)}
                className="font-mono text-sm min-h-[200px]"
                placeholder='{"type": "object", "properties": {...}}'
                readOnly={!isMaster}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
