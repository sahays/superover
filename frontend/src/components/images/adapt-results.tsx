import { useQuery } from '@tanstack/react-query'
import { imageApi } from '@/lib/api-client'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Download, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { ImageJobStatus } from '@/lib/types'

interface AdaptResultsProps {
  jobId: string
  status: ImageJobStatus
}

function SignedImage({ gcsPath, ratio }: { gcsPath: string; ratio: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['signed-url', gcsPath],
    queryFn: () => imageApi.getSignedUrl(gcsPath),
  })

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-100 dark:bg-slate-900">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    )
  }

  return (
    <div className="relative h-full w-full">
      <img
        src={data?.url}
        alt={`Adapt ${ratio}`}
        className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
      />
      <div className="absolute bottom-2 right-2 rounded bg-black/60 px-2 py-1 text-xs font-bold text-white">
        {ratio}
      </div>
    </div>
  )
}

export function AdaptResults({ jobId, status }: AdaptResultsProps) {
  const { data: results, isLoading } = useQuery({
    queryKey: ['image-results', jobId],
    queryFn: () => imageApi.getResults(jobId),
    enabled: status === ImageJobStatus.COMPLETED,
  })

  if (status === ImageJobStatus.PROCESSING || status === ImageJobStatus.PENDING) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
          <h3 className="mt-4 text-lg font-medium">Generating Your Adapts</h3>
          <p className="max-w-md text-sm text-muted-foreground">
            Gemini 3 Pro is creating your cinematic variations. This usually takes 30-60 seconds.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (status === ImageJobStatus.FAILED) {
    return null
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="aspect-video animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold">Generated Variations</h3>
        <Badge variant="outline" className="font-mono">
          {results?.length || 0} Assets
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {results?.map((result: any, index: number) => (
          <Card key={index} className="group overflow-hidden">
            <div className="relative aspect-video overflow-hidden bg-slate-100 dark:bg-slate-950">
              <SignedImage gcsPath={result.gcs_path} ratio={result.aspect_ratio} />
            </div>
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="truncate text-xs font-mono text-muted-foreground">
                  {result.gcs_path.split('/').pop()}
                </div>
                <DownloadButton gcsPath={result.gcs_path} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function DownloadButton({ gcsPath }: { gcsPath: string }) {
  const { data } = useQuery({
    queryKey: ['signed-url', gcsPath],
    queryFn: () => imageApi.getSignedUrl(gcsPath),
  })

  return (
    <Button variant="outline" size="icon" className="h-8 w-8" asChild>
      <a href={data?.url} target="_blank" rel="noreferrer" download>
        <Download className="h-4 w-4" />
      </a>
    </Button>
  )
}
