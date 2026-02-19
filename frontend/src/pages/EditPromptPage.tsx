import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { BotMessageSquare, ArrowLeft, Save, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { promptApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useState, useEffect } from 'react'
import { useToast } from '@/components/ui/use-toast'

interface Prompt {
  prompt_id: string
  prompt_name: string
  prompt_type: string
  prompt_text: string
  updated_at: string
}

export default function EditPromptPage() {
  const navigate = useNavigate()
  const { promptId } = useParams<{ promptId: string }>()
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [promptText, setPromptText] = useState('')

  const { data: prompt, isLoading } = useQuery<Prompt>({
    queryKey: ['prompt', promptId],
    queryFn: () => promptApi.getPrompt(promptId!),
    enabled: !!promptId,
  })

  useEffect(() => {
    if (prompt) {
      setPromptText(prompt.prompt_text)
    }
  }, [prompt])

  const updateMutation = useMutation({
    mutationFn: (newPromptText: string) =>
      promptApi.updatePrompt(promptId!, { prompt_text: newPromptText }),
    onSuccess: () => {
      toast({
        title: 'Prompt Updated',
        description: 'The prompt has been saved successfully.',
      })
      queryClient.invalidateQueries({ queryKey: ['prompt', promptId] })
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      navigate('/prompts')
    },
    onError: (error) => {
      toast({
        title: 'Error',
        description: `Failed to update prompt: ${error.message}`,
        variant: 'destructive',
      })
    },
  })

  const handleSave = () => {
    updateMutation.mutate(promptText)
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Loader2 className="h-12 w-12 animate-spin" />
      </div>
    )
  }

  if (!prompt) {
    return <div>Prompt not found.</div>
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Header */}
      <header className="border-b bg-white/50 backdrop-blur-sm dark:bg-slate-900/50">
        <div className="container mx-auto max-w-6xl px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-600 text-white">
                <BotMessageSquare className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Edit Prompt</h1>
                <p className="text-sm text-muted-foreground">{prompt.prompt_name}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/prompts">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Prompts
                </Button>
              </Link>
              <Button onClick={handleSave} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto max-w-6xl px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Prompt Text</CardTitle>
            <CardDescription>
              Modify the text below. This prompt will be used for all new{' '}
              <strong>{prompt.prompt_type}</strong> jobs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              className="min-h-[500px] font-mono text-sm"
              placeholder="Enter the Gemini prompt text here..."
            />
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
