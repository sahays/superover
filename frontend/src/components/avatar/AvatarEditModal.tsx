import { useEffect, useState } from 'react'
import { Loader2, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { useUpdateAvatar } from '@/lib/api/avatars'
import type { Avatar, AvatarStyle } from '@/types/avatar'
import { STYLE_LABELS, LANGUAGE_OPTIONS } from '@/types/avatar'

const STYLE_OPTIONS: { value: AvatarStyle; description: string }[] = [
  { value: 'to_the_point', description: 'Minimal words, direct, no preamble' },
  { value: 'talkative', description: 'Friendly, warm, expressive' },
  { value: 'funny', description: 'Light, playful, a touch of humor' },
  { value: 'serious', description: 'Measured, factual, no jokes' },
  { value: 'cynical', description: 'Wry, slightly skeptical, dry tone' },
]

interface Props {
  avatar: Avatar
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved?: (patch: Partial<Avatar>) => void
}

export function AvatarEditModal({ avatar, open, onOpenChange, onSaved }: Props) {
  const [name, setName] = useState(avatar.name)
  const [style, setStyle] = useState<AvatarStyle>(avatar.style)
  const [persona, setPersona] = useState(avatar.persona_prompt || '')
  const [behavior, setBehavior] = useState(avatar.behavior_instructions || '')
  const [language, setLanguage] = useState(avatar.language || 'en-US')
  const [grounding, setGrounding] = useState(avatar.enable_grounding)
  const [error, setError] = useState<string | null>(null)

  const update = useUpdateAvatar(avatar.id)

  // Reset local state when the avatar prop changes (e.g. another row opened).
  useEffect(() => {
    setName(avatar.name)
    setStyle(avatar.style)
    setPersona(avatar.persona_prompt || '')
    setBehavior(avatar.behavior_instructions || '')
    setLanguage(avatar.language || 'en-US')
    setGrounding(avatar.enable_grounding)
    setError(null)
  }, [avatar])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const patch = {
        name: name.trim(),
        style,
        persona_prompt: persona.trim(),
        behavior_instructions: behavior.trim(),
        language,
        enable_grounding: grounding,
      }
      await update.mutateAsync(patch)
      onSaved?.(patch)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit avatar</DialogTitle>
          <DialogDescription>Tweak the persona, voice settings and grounding for this avatar.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="avatar-name">Name</Label>
            <Input id="avatar-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>

          <div className="space-y-2">
            <Label>Tone</Label>
            <Select value={style} onValueChange={(v) => setStyle(v as AvatarStyle)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STYLE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div>
                      <div>{STYLE_LABELS[opt.value]}</div>
                      <div className="text-xs text-muted-foreground">{opt.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="avatar-persona">Persona</Label>
            <Textarea
              id="avatar-persona"
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              rows={4}
              placeholder="A senior product manager at a tech startup answering questions about AI."
            />
            <p className="text-xs text-muted-foreground">
              Injected into Gemini's system prompt on every turn.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="avatar-behavior">Behaviour instructions</Label>
            <Textarea
              id="avatar-behavior"
              value={behavior}
              onChange={(e) => setBehavior(e.target.value)}
              rows={4}
              placeholder={
                'Always reply in the same language the user spoke.\n' +
                "Use feminine grammar in Hindi (e.g. 'main aa rahi hoon')."
              }
            />
            <p className="text-xs text-muted-foreground">
              Language-matching, gendered grammar, formality, etc.
            </p>
          </div>

          <div className="space-y-2">
            <Label>Language</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <Label htmlFor="grounding-toggle" className="text-sm">Google Search grounding</Label>
              <p className="text-xs text-muted-foreground">Let the avatar pull live web facts mid-conversation.</p>
            </div>
            <Switch id="grounding-toggle" checked={grounding} onCheckedChange={setGrounding} />
          </div>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending || !name.trim()}>
              {update.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              {update.isPending ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
