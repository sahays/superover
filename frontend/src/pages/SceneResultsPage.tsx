import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Copy, Check, Link2, FileJson, FileText, Coins } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { sceneJobApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function SceneResultsPage() {
  const { id: jobId } = useParams<{ id: string }>()
  const [copied, setCopied] = useState(false)

  const { data: sceneJob, isLoading: isLoadingJob } = useQuery({
    queryKey: ['scene-job', jobId],
    queryFn: () => sceneJobApi.getJob(jobId!),
    enabled: !!jobId,
  })

  const { data: results, isLoading: isLoadingResults } = useQuery({
    queryKey: ['results', jobId],
    queryFn: () => sceneJobApi.getResults(jobId!),
    enabled: sceneJob?.status === 'completed',
  })

  const isLoading = isLoadingJob || isLoadingResults

  // Cost breakup
  const totalTokens = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.total_tokens || 0), 0) || 0
  const totalCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.estimated_cost_usd || 0), 0) || 0
  const totalInputCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.input_cost_usd || 0), 0) || 0
  const totalOutputCost = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.output_cost_usd || 0), 0) || 0
  const promptTokens = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.prompt_tokens || 0), 0) || 0
  const outputTokens = results?.reduce((acc: number, r: any) => acc + (r.result_data?.token_usage?.candidates_tokens || 0), 0) || 0

  // Extract display content from each result
  const chunks = results?.map((r: any, idx: number) => {
    const data = r.result_data
    if (!data) return null
    const textContent = data.subtitle_text || data.raw_text
    return {
      chunk: idx + 1,
      content: textContent || data,
      isText: !!textContent,
    }
  }).filter(Boolean) || []

  const formatContent = (chunk: any): string => {
    if (chunk.isText) return chunk.content
    return JSON.stringify(chunk.content, null, 2)
  }

  const getAllContent = (): string => {
    if (chunks.length === 0) return ''
    if (chunks.length === 1) return formatContent(chunks[0])
    return chunks.map((c: any) => `--- Chunk ${c.chunk} ---\n${formatContent(c)}`).join('\n\n')
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(getAllContent())
    setCopied(true)
    toast.success('Copied to clipboard')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    toast.success('Link copied to clipboard')
  }

  if (isLoading) {
    return (
      <div className="container mx-auto max-w-6xl px-4 py-8">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  if (!sceneJob) {
    return (
      <div className="container mx-auto max-w-6xl px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold">Job not found</h2>
            <Link to="/scene-analysis">
              <Button className="mt-4" variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Scene Analysis
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (sceneJob.status !== 'completed') {
    return (
      <div className="container mx-auto max-w-6xl px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold">Results not ready</h2>
            <p className="mt-2 text-muted-foreground">Job status: {sceneJob.status}</p>
            <Link to={`/scene/${jobId}`}>
              <Button className="mt-4" variant="outline">View Job Details</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to={`/scene/${jobId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold font-heading">Analysis Results</h1>
            <p className="text-sm text-muted-foreground">
              {sceneJob.prompt_name || 'Scene Analysis'}
              {' • '}
              {chunks.length} chunk(s)
              {sceneJob.config?.model && ` • ${sceneJob.config.model}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCopyLink}>
            <Link2 className="mr-2 h-4 w-4" />
            Copy Link
          </Button>
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
            {copied ? 'Copied' : 'Copy All'}
          </Button>
        </div>
      </div>

      {/* Cost & Info Bar */}
      <div className="flex flex-wrap gap-4 text-sm">
        {totalCost > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg border px-3 py-2">
            <Coins className="h-4 w-4 text-green-600" />
            <span className="font-mono font-medium">${totalCost.toFixed(4)}</span>
            <span className="text-muted-foreground ml-1">
              (In: <span className="font-mono">${totalInputCost.toFixed(4)}</span> | Out: <span className="font-mono">${totalOutputCost.toFixed(4)}</span>)
            </span>
          </div>
        )}
        {totalTokens > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-muted-foreground">
            Tokens: <span className="font-mono">{promptTokens.toLocaleString()}</span> in / <span className="font-mono">{outputTokens.toLocaleString()}</span> out
            <span className="mx-1">=</span>
            <span className="font-mono font-medium text-foreground">{totalTokens.toLocaleString()}</span>
          </div>
        )}
        {sceneJob.prompt_id && (
          <Link
            to={`/prompts/${sceneJob.prompt_id}`}
            className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
          >
            <FileText className="h-4 w-4" />
            View Prompt & Schema
          </Link>
        )}
      </div>

      {/* Results */}
      {chunks.length > 0 ? (
        chunks.map((chunk: any) => (
          <Card key={chunk.chunk}>
            {chunks.length > 1 && (
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  {chunk.isText ? (
                    <FileText className="h-4 w-4 text-green-500" />
                  ) : (
                    <FileJson className="h-4 w-4 text-blue-500" />
                  )}
                  Chunk {chunk.chunk}
                </CardTitle>
              </CardHeader>
            )}
            <CardContent className={chunks.length === 1 ? 'pt-6' : ''}>
              <pre className="whitespace-pre-wrap text-sm font-mono bg-muted rounded-lg p-4 overflow-x-auto max-h-[80vh] overflow-y-auto">
                {formatContent(chunk)}
              </pre>
            </CardContent>
          </Card>
        ))
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No results available</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
