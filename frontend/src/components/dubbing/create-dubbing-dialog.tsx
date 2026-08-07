import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Languages, Sparkles, Volume2, Mic, Upload, Check, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { videoApi, dubbingApi, uploadToGCS } from '@/lib/api-client'
import { DubbingLanguage, DubbingMode } from '@/lib/types'
import { toast } from 'sonner'

const TARGET_LANGUAGES = [
  { code: DubbingLanguage.HINDI, name: 'Hindi', native: 'हिन्दी', flag: '🇮🇳' },
  { code: DubbingLanguage.ENGLISH, name: 'English', native: 'English (US)', flag: '🇺🇸' },
  { code: DubbingLanguage.PORTUGUESE, name: 'Portuguese', native: 'Português', flag: '🇧🇷' },
  { code: DubbingLanguage.SPANISH, name: 'Spanish', native: 'Español', flag: '🇪🇸' },
  { code: DubbingLanguage.GERMAN, name: 'German', native: 'Deutsch', flag: '🇩🇪' },
]

const VOICE_PRESETS = [
  { name: 'Kore', gender: 'Female', description: 'Warm, natural & articulate' },
  { name: 'Puck', gender: 'Male', description: 'Energetic, dynamic & friendly' },
  { name: 'Aoede', gender: 'Female', description: 'Expressive, clear & broadcast-ready' },
  { name: 'Charon', gender: 'Male', description: 'Authoritative, deep & calm' },
  { name: 'Fenrir', gender: 'Male', description: 'Casual, conversational & relatable' },
]

interface CreateDubbingDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialVideoId?: string
}

export function CreateDubbingDialog({ open, onOpenChange, initialVideoId }: CreateDubbingDialogProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedVideoId, setSelectedVideoId] = useState<string>(initialVideoId || '')
  const [selectedLanguages, setSelectedLanguages] = useState<DubbingLanguage[]>([
    DubbingLanguage.HINDI,
    DubbingLanguage.SPANISH,
  ])
  const [selectedVoice, setSelectedVoice] = useState<string>('Kore')
  const [dubbingMode, setDubbingMode] = useState<DubbingMode>(DubbingMode.VOICEOVER)
  const [duckingDb, setDuckingDb] = useState<number>(-18)
  const [sourceLanguage, setSourceLanguage] = useState<string>('auto')

  // Upload file state
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  // Fetch available uploaded videos
  const { data: videos, isLoading: loadingVideos } = useQuery({
    queryKey: ['videos-list-for-dubbing'],
    queryFn: () => videoApi.listVideos(100),
    enabled: open,
  })

  const toggleLanguage = (lang: DubbingLanguage) => {
    setSelectedLanguages((prev) =>
      prev.includes(lang) ? prev.filter((l) => l !== lang) : [...prev, lang]
    )
  }

  const createJobMutation = useMutation({
    mutationFn: async () => {
      let videoIdToUse = selectedVideoId

      // Upload file directly if selected
      if (uploadFile) {
        setIsUploading(true)
        try {
          const { signed_url, gcs_path } = await videoApi.getSignedUrl(
            uploadFile.name,
            uploadFile.type || 'video/mp4'
          )
          await uploadToGCS(signed_url, uploadFile)
          const newVideo = await videoApi.createVideo({
            filename: uploadFile.name,
            gcs_path,
            content_type: uploadFile.type || 'video/mp4',
            size_bytes: uploadFile.size,
          })
          videoIdToUse = newVideo.video_id
        } finally {
          setIsUploading(false)
        }
      }

      if (!videoIdToUse) {
        throw new Error('Please select an existing video or upload a new file.')
      }

      if (selectedLanguages.length === 0) {
        throw new Error('Please select at least one target language for dubbing.')
      }

      return dubbingApi.createJob({
        video_id: videoIdToUse,
        config: {
          target_languages: selectedLanguages,
          voice: selectedVoice,
          mode: dubbingMode,
          ducking_db: duckingDb,
          source_language: sourceLanguage,
        },
      })
    },
    onSuccess: (newJob) => {
      toast.success('Dubbing job initiated', {
        description: `Multilingual translation started for ${selectedLanguages.length} language(s).`,
      })
      queryClient.invalidateQueries({ queryKey: ['dubbing-jobs'] })
      onOpenChange(false)
      navigate(`/dubbing/${newJob.job_id}`)
    },
    onError: (err: any) => {
      toast.error('Failed to start dubbing', {
        description: err.response?.data?.detail || err.message || 'An error occurred.',
      })
    },
  })

  const isPending = createJobMutation.isPending || isUploading

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Languages className="h-6 w-6" />
            </div>
            <div>
              <DialogTitle className="text-xl font-heading">AI Video Dubbing Studio</DialogTitle>
              <DialogDescription>
                Translate spoken dialogue into Hindi, English, Portuguese, Spanish, or German using Gemini Live voice synthesis.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Source Video Selection */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold flex items-center gap-2">
              <Volume2 className="h-4 w-4 text-primary" />
              1. Select Video Asset
            </Label>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Select
                  value={selectedVideoId}
                  onValueChange={(val) => {
                    setSelectedVideoId(val)
                    setUploadFile(null)
                  }}
                  disabled={loadingVideos || !!uploadFile}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={loadingVideos ? 'Loading library...' : 'Choose from library...'} />
                  </SelectTrigger>
                  <SelectContent>
                    {videos?.map((v: any) => (
                      <SelectItem key={v.video_id} value={v.video_id}>
                        {v.filename || v.video_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center">
                <label className="flex flex-1 items-center justify-center gap-2 border border-dashed rounded-lg p-2.5 cursor-pointer hover:bg-muted/50 transition-colors text-xs text-muted-foreground">
                  <Upload className="h-4 w-4" />
                  <span className="truncate">
                    {uploadFile ? uploadFile.name : 'Or upload new video'}
                  </span>
                  <input
                    type="file"
                    accept="video/*,audio/*"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) {
                        setUploadFile(e.target.files[0])
                        setSelectedVideoId('')
                      }
                    }}
                  />
                </label>
              </div>
            </div>
          </div>

          {/* Target Languages */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <Languages className="h-4 w-4 text-primary" />
                2. Target Dubbing Languages ({selectedLanguages.length} selected)
              </Label>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {TARGET_LANGUAGES.map((lang) => {
                const isSelected = selectedLanguages.includes(lang.code)
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => toggleLanguage(lang.code)}
                    className={`flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/10 ring-1 ring-primary'
                        : 'border-border hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{lang.flag}</span>
                      <div>
                        <div className="text-sm font-medium">{lang.name}</div>
                        <div className="text-xs text-muted-foreground">{lang.native}</div>
                      </div>
                    </div>
                    {isSelected && <Check className="h-4 w-4 text-primary" />}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Voice Persona & Style */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold flex items-center gap-2">
              <Mic className="h-4 w-4 text-primary" />
              3. Voice Persona Preset
            </Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {VOICE_PRESETS.map((voice) => {
                const isSelected = selectedVoice === voice.name
                return (
                  <button
                    key={voice.name}
                    type="button"
                    onClick={() => setSelectedVoice(voice.name)}
                    className={`flex items-start justify-between p-3 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/10 ring-1 ring-primary'
                        : 'border-border hover:bg-muted/40'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">{voice.name}</span>
                        <Badge variant="outline" className="text-[10px] py-0">
                          {voice.gender}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{voice.description}</p>
                    </div>
                    {isSelected && <Check className="h-4 w-4 text-primary shrink-0" />}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Mixing Mode & Ducking */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">Audio Mix Strategy</Label>
              <Select value={dubbingMode} onValueChange={(v) => setDubbingMode(v as DubbingMode)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DubbingMode.VOICEOVER}>Voiceover with background ducking (-18dB)</SelectItem>
                  <SelectItem value={DubbingMode.REPLACE}>Full dialogue replacement (Clean speech)</SelectItem>
                  <SelectItem value={DubbingMode.ISOLATED}>Isolated speech track only</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-medium">Source Language</Label>
              <Select value={sourceLanguage} onValueChange={setSourceLanguage}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto Detect</SelectItem>
                  <SelectItem value="en-US">English (US)</SelectItem>
                  <SelectItem value="hi-IN">Hindi</SelectItem>
                  <SelectItem value="es-ES">Spanish</SelectItem>
                  <SelectItem value="pt-BR">Portuguese</SelectItem>
                  <SelectItem value="de-DE">German</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={() => createJobMutation.mutate()}
            disabled={isPending || (!selectedVideoId && !uploadFile) || selectedLanguages.length === 0}
            className="gap-2"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {isUploading ? 'Uploading Video...' : 'Starting Dubbing...'}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Start Multilingual Dubbing
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
