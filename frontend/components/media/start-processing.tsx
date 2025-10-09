'use client'

import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { mediaApi } from '@/lib/api-client'
import { MediaProcessingConfig } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

interface StartProcessingProps {
  videoId: string
  onSuccess?: () => void
  onCancel?: () => void
}

export function StartProcessing({ videoId, onSuccess, onCancel }: StartProcessingProps) {
  const [config, setConfig] = useState<MediaProcessingConfig>({
    compress: true,
    compress_resolution: '480p',
    extract_audio: true,
    audio_format: 'mp3',
    audio_bitrate: '128k',
    crf: 23,
    preset: 'medium',
  })

  const { data: presets } = useQuery({
    queryKey: ['media-presets'],
    queryFn: () => mediaApi.getPresets(),
  })

  const createJobMutation = useMutation({
    mutationFn: () => mediaApi.createJob({ video_id: videoId, config }),
    onSuccess: () => {
      onSuccess?.()
    },
  })

  return (
    <div className="space-y-6">
      {!createJobMutation.isSuccess && !createJobMutation.isPending && (
        <>
          <div className="space-y-4">
            {/* Compression Settings */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="compress">Enable Compression</Label>
                <Switch
                  id="compress"
                  checked={config.compress}
                  onCheckedChange={(checked) => setConfig({ ...config, compress: checked })}
                />
              </div>

              {config.compress && (
                <div className="space-y-2 pl-4">
                  <Label htmlFor="resolution">Resolution</Label>
                  <Select
                    value={config.compress_resolution}
                    onValueChange={(value) => setConfig({ ...config, compress_resolution: value })}
                  >
                    <SelectTrigger id="resolution">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {presets?.resolutions.map((res: string) => (
                        <SelectItem key={res} value={res}>
                          {res}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>

            {/* Audio Settings */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="audio">Extract Audio</Label>
                <Switch
                  id="audio"
                  checked={config.extract_audio}
                  onCheckedChange={(checked) => setConfig({ ...config, extract_audio: checked })}
                />
              </div>

              {config.extract_audio && (
                <div className="grid gap-4 pl-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="audio-format">Format</Label>
                    <Select
                      value={config.audio_format}
                      onValueChange={(value) => setConfig({ ...config, audio_format: value })}
                    >
                      <SelectTrigger id="audio-format">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {presets?.audio_formats.map((format: string) => (
                          <SelectItem key={format} value={format}>
                            {format.toUpperCase()}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="audio-bitrate">Bitrate</Label>
                    <Select
                      value={config.audio_bitrate}
                      onValueChange={(value) => setConfig({ ...config, audio_bitrate: value })}
                    >
                      <SelectTrigger id="audio-bitrate">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {presets?.audio_bitrates.map((bitrate: string) => (
                          <SelectItem key={bitrate} value={bitrate}>
                            {bitrate}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={() => createJobMutation.mutate()}
              disabled={createJobMutation.isPending}
              className="flex-1"
            >
              Start Processing
            </Button>
            {onCancel && (
              <Button variant="outline" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </>
      )}

      {/* Processing */}
      {createJobMutation.isPending && (
        <div className="flex items-center justify-center rounded-lg border p-8">
          <div className="text-center">
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
            <h3 className="mt-4 text-lg font-semibold">Starting processing...</h3>
          </div>
        </div>
      )}

      {/* Success */}
      {createJobMutation.isSuccess && (
        <div className="flex items-center justify-center rounded-lg border border-green-200 bg-green-50 p-8">
          <div className="text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-green-600" />
            <h3 className="mt-4 text-lg font-semibold text-green-900">
              Processing Job Created!
            </h3>
            <p className="mt-2 text-sm text-green-700">
              The worker will process this job shortly.
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {createJobMutation.isError && (
        <div className="space-y-4">
          <div className="flex items-center justify-center rounded-lg border border-red-200 bg-red-50 p-8">
            <div className="text-center">
              <AlertCircle className="mx-auto h-12 w-12 text-red-600" />
              <h3 className="mt-4 text-lg font-semibold text-red-900">Failed to Create Job</h3>
              <p className="mt-2 text-sm text-red-700">
                {createJobMutation.error instanceof Error
                  ? createJobMutation.error.message
                  : 'Unknown error'}
              </p>
            </div>
          </div>
          <Button
            onClick={() => createJobMutation.reset()}
            variant="outline"
            className="w-full"
          >
            Try Again
          </Button>
        </div>
      )}
    </div>
  )
}
