import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Languages,
  Sparkles,
  Volume2,
  Mic,
  Upload,
  Check,
  Loader2,
  Film,
  Sliders,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { videoApi, dubbingApi, uploadToGCS } from '@/lib/api-client'
import { DubbingLanguage, DubbingMode, Video } from '@/lib/types'
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

export default function DubbingNewPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedVideoId, setSelectedVideoId] = useState<string>('')
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
    queryKey: ['videos-list-for-dubbing-page'],
    queryFn: () => videoApi.listVideos(100),
  })

  const videoList: any[] = Array.isArray(videos)
    ? videos
    : Array.isArray((videos as any)?.items)
      ? (videos as any).items
      : []

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
    <div className="container mx-auto px-4 py-8 max-w-4xl space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/dubbing">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold font-heading">New Dubbing Studio</h1>
            <Badge variant="outline" className="border-amber-500/40 text-amber-400 bg-amber-500/10">
              <Sparkles className="h-3 w-3 mr-1" /> Gemini Multimodal Live
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">
            Translate spoken dialogue into natural, timestamp-synchronized multi-track audio.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Source Video Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Film className="h-5 w-5 text-primary" /> 1. Select or Upload Video
            </CardTitle>
            <CardDescription>
              Choose a processed scene or upload a raw video clip to extract dialogue from.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Choose Existing Video</Label>
                <Select
                  value={selectedVideoId}
                  onValueChange={(val) => {
                    setSelectedVideoId(val)
                    setUploadFile(null)
                  }}
                  disabled={loadingVideos || !!uploadFile}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select existing video..." />
                  </SelectTrigger>
                  <SelectContent>
                    {videoList.map((v) => (
                      <SelectItem key={v.video_id} value={v.video_id}>
                        {v.filename || v.video_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Or Upload New File</Label>
                <div className="flex items-center gap-2">
                  <InputFileButton
                    file={uploadFile}
                    onFileChange={(f) => {
                      setUploadFile(f)
                      if (f) setSelectedVideoId('')
                    }}
                  />
                  {uploadFile && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setUploadFile(null)}
                    >
                      Clear
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Target Languages */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Languages className="h-5 w-5 text-primary" /> 2. Target Languages
            </CardTitle>
            <CardDescription>
              Select the languages to transcribe and generate synchronized speech tracks for.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {TARGET_LANGUAGES.map((lang) => {
                const isSelected = selectedLanguages.includes(lang.code)
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => toggleLanguage(lang.code)}
                    className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/10 shadow-sm'
                        : 'border-border/60 hover:border-border hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="text-2xl">{lang.flag}</span>
                      <div>
                        <div className="text-sm font-semibold">{lang.name}</div>
                        <div className="text-xs text-muted-foreground">{lang.native}</div>
                      </div>
                    </div>
                    {isSelected && (
                      <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
                        <Check className="h-3 w-3" />
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
            {selectedLanguages.length === 0 && (
              <p className="text-xs text-amber-500 mt-2">
                * Please select at least one target language to begin dubbing.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Voice Profile & Audio Mix */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mic className="h-5 w-5 text-primary" /> 3. Voice Actor & Audio Mix
            </CardTitle>
            <CardDescription>
              Customize the synthetic voice timbre and background audio ducking level.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <Label>Voice Timbre Preset</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {VOICE_PRESETS.map((voice) => {
                  const isSelected = selectedVoice === voice.name
                  return (
                    <button
                      key={voice.name}
                      type="button"
                      onClick={() => setSelectedVoice(voice.name)}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        isSelected
                          ? 'border-primary bg-primary/10 shadow-sm'
                          : 'border-border/60 hover:bg-muted/40'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-sm">{voice.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {voice.gender}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">{voice.description}</p>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t">
              <div className="space-y-2">
                <Label>Dubbing Blend Mode</Label>
                <Select
                  value={dubbingMode}
                  onValueChange={(val) => setDubbingMode(val as DubbingMode)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={DubbingMode.VOICEOVER}>
                      Voiceover (Lowers original audio background)
                    </SelectItem>
                    <SelectItem value={DubbingMode.REPLACE}>
                      Complete Replacement (Mutes original audio)
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {dubbingMode === DubbingMode.VOICEOVER && (
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Background Ducking Volume</Label>
                    <span className="text-xs font-mono text-muted-foreground">{duckingDb} dB</span>
                  </div>
                  <input
                    type="range"
                    min="-30"
                    max="-6"
                    step="1"
                    value={duckingDb}
                    onChange={(e) => setDuckingDb(Number(e.target.value))}
                    className="w-full accent-primary cursor-pointer"
                  />
                  <p className="text-xs text-muted-foreground">
                    Level original video background sound drops during translated dialogue.
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-4">
          <Button variant="outline" asChild disabled={isPending}>
            <Link to="/dubbing">Cancel</Link>
          </Button>
          <Button
            onClick={() => createJobMutation.mutate()}
            disabled={isPending || (!selectedVideoId && !uploadFile) || selectedLanguages.length === 0}
            className="min-w-[160px]"
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isUploading ? 'Uploading Video...' : 'Initiating Job...'}
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" /> Start AI Dubbing
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

function InputFileButton({
  file,
  onFileChange,
}: {
  file: File | null
  onFileChange: (file: File | null) => void
}) {
  return (
    <label className="flex items-center gap-2 px-3 py-2 border rounded-md cursor-pointer hover:bg-muted/40 transition-colors text-sm w-full">
      <Upload className="h-4 w-4 text-muted-foreground shrink-0" />
      <span className="truncate flex-1 text-muted-foreground">
        {file ? file.name : 'Choose video file (MP4, MOV)...'}
      </span>
      <input
        type="file"
        accept="video/mp4,video/quicktime,video/webm"
        className="hidden"
        onChange={(e) => {
          const files = e.target.files
          if (files && files[0]) {
            onFileChange(files[0])
          }
        }}
      />
    </label>
  )
}
