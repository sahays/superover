import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ArrowLeft, FileSpreadsheet, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { engagementApi, videoApi } from '@/lib/api-client'
import { EligibleSourceJob, Video } from '@/lib/types'
import { UploadBarc } from '@/components/engagement/upload-barc'

export default function EngagementNewPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [sourceJobId, setSourceJobId] = useState<string>('')
  const [barcGcsPath, setBarcGcsPath] = useState<string | null>(null)
  const [barcFilename, setBarcFilename] = useState<string | null>(null)
  const [videoFilenames, setVideoFilenames] = useState<Record<string, string>>({})

  const { data: videos } = useQuery({
    queryKey: ['videos-for-engagement-new'],
    queryFn: () => videoApi.listVideos(50) as Promise<Video[]>,
  })

  useEffect(() => {
    if (!videos) return
    const map: Record<string, string> = {}
    for (const v of videos) map[v.video_id] = v.filename
    setVideoFilenames((prev) => ({ ...prev, ...map }))
  }, [videos])

  const { data: sourceJobs, isLoading: loadingSource } = useQuery({
    queryKey: ['all-eligible-source-jobs'],
    queryFn: () => engagementApi.listAllEligibleSourceJobs(100) as Promise<EligibleSourceJob[]>,
  })

  const selectedJob = (sourceJobs || []).find((j) => j.job_id === sourceJobId)

  const createMutation = useMutation({
    mutationFn: (data: { video_id: string; source_scene_job_id: string; barc_gcs_path: string }) =>
      engagementApi.createJob(data),
    onSuccess: () => {
      toast.success('Engagement analysis queued')
      queryClient.invalidateQueries({ queryKey: ['engagement-jobs'] })
      navigate('/engagement')
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail || 'Failed to create job'
      toast.error(detail)
    },
  })

  const ready = !!sourceJobId && !!barcGcsPath && !!selectedJob

  const formatJobLabel = (j: EligibleSourceJob) => {
    const filename = videoFilenames[j.video_id] || j.video_id.slice(0, 8)
    const promptName = j.prompt_name || 'Scene Analysis'
    const typeSuffix = j.prompt_type && j.prompt_type !== 'scene_analysis' ? ` [${j.prompt_type}]` : ''
    return `${filename} — ${promptName}${typeSuffix}`
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6">
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/engagement">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to engagement
          </Link>
        </Button>
        <h1 className="text-3xl font-bold font-heading">New Engagement Analysis</h1>
        <p className="mt-1 text-muted-foreground">
          Pair a completed Scene Analysis job with BARC engagement data to surface peaks and valleys.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configure analysis</CardTitle>
          <CardDescription>
            We'll use the chunked scene-analysis context to explain why each peak and valley happened.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium">1. Source Scene Analysis job</label>
            <Select value={sourceJobId} onValueChange={setSourceJobId} disabled={loadingSource}>
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    loadingSource ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="h-3 w-3 animate-spin" /> Loading…
                      </span>
                    ) : sourceJobs && sourceJobs.length === 0 ? (
                      'No completed Scene Analysis jobs available'
                    ) : (
                      'Select a completed Scene Analysis job'
                    )
                  }
                >
                  {selectedJob && (
                    <span className="block truncate">{formatJobLabel(selectedJob)}</span>
                  )}
                </SelectValue>
              </SelectTrigger>
              <SelectContent className="max-w-[var(--radix-select-trigger-width)]">
                {(sourceJobs || []).map((j) => (
                  <SelectItem key={j.job_id} value={j.job_id}>
                    <span className="block truncate">{formatJobLabel(j)}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedJob && (
              <p className="text-xs text-muted-foreground truncate">
                Job {selectedJob.job_id.slice(0, 8)}
                {selectedJob.created_at
                  ? ` · ${new Date(selectedJob.created_at).toLocaleString()}`
                  : ''}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">2. BARC engagement file</label>
            <UploadBarc
              uploadedGcsPath={barcGcsPath}
              uploadedFilename={barcFilename}
              onUploaded={(path, name) => {
                setBarcGcsPath(path)
                setBarcFilename(name)
              }}
              onClear={() => {
                setBarcGcsPath(null)
                setBarcFilename(null)
              }}
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-4 border-t">
            <Button asChild variant="outline">
              <Link to="/engagement">Cancel</Link>
            </Button>
            <Button
              disabled={!ready || createMutation.isPending}
              onClick={() => {
                if (!ready || !selectedJob) return
                createMutation.mutate({
                  video_id: selectedJob.video_id,
                  source_scene_job_id: selectedJob.job_id,
                  barc_gcs_path: barcGcsPath!,
                })
              }}
            >
              {createMutation.isPending ? 'Creating…' : (
                <>
                  <FileSpreadsheet className="mr-2 h-4 w-4" />
                  Start analysis
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
