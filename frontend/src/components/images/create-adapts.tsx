import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { promptApi, imageApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Loader2, Wand2, Image as ImageIcon } from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'

const ASPECT_RATIOS = [
  { id: '16:9', label: '16:9 (Landscape)', icon: '📺' },
  { id: '9:16', label: '9:16 (Vertical)', icon: '📱' },
  { id: '1:1', label: '1:1 (Square)', icon: '⬛' },
  { id: '4:5', label: '4:5 (Social)', icon: '📸' },
  { id: '2:3', label: '2:3 (Poster)', icon: '🖼️' },
  { id: '21:9', label: '21:9 (Ultrawide)', icon: '🎬' },
]

const RESOLUTIONS = ['HD', '4K', 'Original']

interface CreateAdaptsProps {
  videoId: string
  onJobCreated?: (jobId: string) => void
}

export function CreateAdapts({ videoId, onJobCreated }: CreateAdaptsProps) {
  const { toast } = useToast()
  const [selectedRatios, setSelectedRatios] = useState<string[]>(['16:9', '9:16', '1:1'])
  const [resolution, setResolution] = useState('HD')
  const [promptId, setPromptId] = useState<string>('')

  const { data: prompts } = useQuery({
    queryKey: ['prompts', 'image_adaptation'],
    queryFn: async () => {
      const allPrompts = await promptApi.listPrompts()
      return allPrompts.filter((p: any) => p.type === 'image_adaptation' || p.type === 'custom')
    },
  })

  const createJobMutation = useMutation({
    mutationFn: (data: {
      video_id: string
      prompt_id: string
      config: { aspect_ratios: string[]; resolution: string }
    }) => imageApi.createJob(data),
    onSuccess: (data) => {
      toast({
        title: 'Job Created',
        description: 'Generative image adaptation has started.',
      })
      if (onJobCreated) onJobCreated(data.job_id)
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to start job.',
        variant: 'destructive',
      })
    },
  })

  const toggleRatio = (id: string) => {
    setSelectedRatios((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    )
  }

  const handleStart = () => {
    if (!promptId) {
      toast({
        title: 'Selection Required',
        description: 'Please select an adaptation prompt.',
        variant: 'destructive',
      })
      return
    }
    if (selectedRatios.length === 0) {
      toast({
        title: 'Selection Required',
        description: 'Please select at least one aspect ratio.',
        variant: 'destructive',
      })
      return
    }

    createJobMutation.mutate({
      video_id: videoId,
      prompt_id: promptId,
      config: {
        aspect_ratios: selectedRatios,
        resolution,
      },
    })
  }

  return (
    <Card className="border-blue-200 bg-blue-50/30 dark:border-blue-900/30 dark:bg-blue-900/10">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Wand2 className="h-5 w-5 text-blue-600" />
          <CardTitle>Create Image Adapts</CardTitle>
        </div>
        <CardDescription>
          Generate new variations of this image using Gemini 3 Pro generative AI.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Aspect Ratios */}
        <div className="space-y-3">
          <Label className="text-base">Target Aspect Ratios</Label>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {ASPECT_RATIOS.map((ratio) => (
              <div
                key={ratio.id}
                className={`flex items-center space-x-2 rounded-md border p-3 transition-colors ${
                  selectedRatios.includes(ratio.id)
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'bg-white dark:bg-slate-900'
                }`}
              >
                <Checkbox
                  id={`ratio-${ratio.id}`}
                  checked={selectedRatios.includes(ratio.id)}
                  onCheckedChange={() => toggleRatio(ratio.id)}
                />
                <label
                  htmlFor={`ratio-${ratio.id}`}
                  className="flex flex-1 cursor-pointer items-center text-sm font-medium leading-none"
                >
                  <span className="mr-2">{ratio.icon}</span>
                  {ratio.label}
                </label>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          {/* Resolution */}
          <div className="space-y-3">
            <Label>Output Resolution</Label>
            <Select value={resolution} onValueChange={setResolution}>
              <SelectTrigger>
                <SelectValue placeholder="Select resolution" />
              </SelectTrigger>
              <SelectContent>
                {RESOLUTIONS.map((res) => (
                  <SelectItem key={res} value={res}>
                    {res}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Prompt */}
          <div className="space-y-3">
            <Label>Adaptation Prompt</Label>
            <Select value={promptId} onValueChange={setPromptId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a prompt" />
              </SelectTrigger>
              <SelectContent>
                {prompts?.map((prompt: any) => (
                  <SelectItem key={prompt.prompt_id} value={prompt.prompt_id}>
                    {prompt.name}
                  </SelectItem>
                ))}
                {prompts?.length === 0 && (
                  <SelectItem value="none" disabled>
                    No adaptation prompts found
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Button
          className="w-full"
          size="lg"
          disabled={createJobMutation.isPending}
          onClick={handleStart}
        >
          {createJobMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Starting Generation...
            </>
          ) : (
            <>
              <Wand2 className="mr-2 h-4 w-4" />
              Generate All Adapts
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  )
}
