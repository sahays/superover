import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useCreateAvatar } from '@/lib/api/avatars'
import {
  LANGUAGE_OPTIONS,
  PRESET_CATALOG,
  STYLE_LABELS,
  VOICE_CATALOG,
  type AvatarStyle,
  type AvatarVoice,
} from '@/types/avatar'

const STYLE_VALUES: AvatarStyle[] = ['to_the_point', 'talkative', 'funny', 'serious', 'cynical']

export default function AvatarCreatePage() {
  const navigate = useNavigate()
  const create = useCreateAvatar()

  const [presetId, setPresetId] = useState<string>(PRESET_CATALOG[0].id)
  const [name, setName] = useState<string>(PRESET_CATALOG[0].displayName)
  const [voice, setVoice] = useState<AvatarVoice>('Kore')
  const [style, setStyle] = useState<AvatarStyle>('to_the_point')
  const [persona, setPersona] = useState('')
  const [language, setLanguage] = useState('en-US')
  const [greeting, setGreeting] = useState(PRESET_CATALOG[0].defaultGreeting)
  const [grounding, setGrounding] = useState(false)

  const onPresetChange = (id: string) => {
    setPresetId(id)
    const preset = PRESET_CATALOG.find((p) => p.id === id)
    if (preset) {
      setName(preset.displayName)
      setGreeting(preset.defaultGreeting)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const created = await create.mutateAsync({
        name: name.trim(),
        preset_name: presetId,
        voice,
        style,
        persona_prompt: persona.trim(),
        language,
        default_greeting: greeting.trim(),
        enable_grounding: grounding,
      })
      toast.success('Avatar created')
      navigate(`/avatars/${created.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create avatar')
    }
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <Link
        to="/avatars"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft size={14} /> Back to Avatars
      </Link>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" /> New Avatar
          </CardTitle>
          <CardDescription>
            Pick a preset face, give it a persona and a voice, and you're ready to talk.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label>Preset</Label>
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
                {PRESET_CATALOG.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => onPresetChange(p.id)}
                    className={`rounded-lg overflow-hidden border-2 transition-colors ${
                      presetId === p.id ? 'border-primary' : 'border-transparent hover:border-muted-foreground/40'
                    }`}
                    title={`${p.displayName} — ${p.mood}`}
                  >
                    <img src={p.imageUrl} alt={p.displayName} className="aspect-[3/4] w-full object-cover" />
                    <div className="text-xs py-1.5 truncate">{p.displayName}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="avatar-name">Name</Label>
                <Input id="avatar-name" value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label>Voice</Label>
                <Select value={voice} onValueChange={(v) => setVoice(v as AvatarVoice)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {VOICE_CATALOG.map((v) => (
                      <SelectItem key={v.id} value={v.id}>
                        {v.id} <span className="text-muted-foreground">— {v.description} ({v.gender})</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Tone</Label>
                <Select value={style} onValueChange={(v) => setStyle(v as AvatarStyle)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STYLE_VALUES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {STYLE_LABELS[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Language</Label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LANGUAGE_OPTIONS.map((l) => (
                      <SelectItem key={l.value} value={l.value}>
                        {l.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="avatar-persona">Persona prompt</Label>
              <Textarea
                id="avatar-persona"
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                rows={3}
                placeholder="A senior cricket analyst who loves explaining the strategic side of the game."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="avatar-greeting">Opening greeting</Label>
              <Input
                id="avatar-greeting"
                value={greeting}
                onChange={(e) => setGreeting(e.target.value)}
                placeholder="Hi! Ready to talk cricket?"
              />
              <p className="text-xs text-muted-foreground">
                The avatar speaks this exact line when the session opens. Leave blank to let the model decide.
              </p>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label htmlFor="grounding-toggle" className="text-sm">Google Search grounding</Label>
                <p className="text-xs text-muted-foreground">Pull live web facts during the conversation.</p>
              </div>
              <Switch id="grounding-toggle" checked={grounding} onCheckedChange={setGrounding} />
            </div>

            <div className="flex justify-end gap-2">
              <Link to="/avatars">
                <Button type="button" variant="ghost">Cancel</Button>
              </Link>
              <Button type="submit" disabled={create.isPending || !name.trim()}>
                {create.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create avatar
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
