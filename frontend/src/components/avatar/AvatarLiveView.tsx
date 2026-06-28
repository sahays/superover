// Live avatar UI. Wires the live session hook to a canvas + a small text/mute
// control bar. All session lifecycle lives in `useAvatarLiveSession` — this
// component is purely UI.

import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Loader2, Mic, MicOff, Pencil, Power, Send } from 'lucide-react'
import { useAuthStore } from '@/store/useAuthStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AvatarEditModal } from '@/components/avatar/AvatarEditModal'
import { type AvatarLiveStatus, useAvatarLiveSession } from '@/hooks/useAvatarLiveSession'
import type { Avatar } from '@/types/avatar'

interface Props {
  avatar: Avatar
}

export function AvatarLiveView({ avatar }: Props) {
  const { isMaster, isAdmin } = useAuthStore()
  const elevated = isMaster || isAdmin

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [muted, setMuted] = useState(false)
  const [textInput, setTextInput] = useState('')
  const [editing, setEditing] = useState(false)
  // Set true when the user explicitly disconnects; suppresses the auto-start
  // hook from spinning a fresh session right back up.
  const [disconnected, setDisconnected] = useState(false)

  const live = useAvatarLiveSession({
    avatarId: avatar.id,
    enabled: elevated && !disconnected,
    canvasRef,
  })

  // Capture starts muted by default; sync our local mute state to it once
  // the capture is actually created (on session connect).
  useEffect(() => {
    live.captureRef.current?.setMuted(muted)
  }, [muted, live.captureRef, live.status])

  const handleDisconnect = () => {
    live.teardown()
    live.setStatus('closed')
    setDisconnected(true)
  }

  const handleReconnect = () => {
    live.setError(null)
    setDisconnected(false)
  }

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault()
    const text = textInput.trim()
    if (!text || !live.sessionRef.current?.isConnected()) return
    // Real user gesture — unblock the audio AudioContext if browser autoplay
    // policy parked it in 'suspended' state.
    void live.sinkRef.current?.resume()
    void live.audioPlayerRef.current?.resume()
    live.sessionRef.current.sendText(text)
    setTextInput('')
  }

  const toggleMute = () => {
    const next = !muted
    setMuted(next)
    live.captureRef.current?.setMuted(next)
    void live.sinkRef.current?.resume()
    void live.audioPlayerRef.current?.resume()
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8 space-y-6">
      <Link
        to="/avatars"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft size={14} /> Back to Avatars
      </Link>

      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-2xl font-bold tracking-tight truncate">{avatar.name}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Gemini Live · {avatar.voice}
            {avatar.persona_prompt
              ? ` · ${avatar.persona_prompt.slice(0, 64)}${avatar.persona_prompt.length > 64 ? '…' : ''}`
              : ''}
          </p>
        </div>
        {elevated && (
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="mr-1.5 h-3 w-3" /> Edit
          </Button>
        )}
      </div>

      <AvatarEditModal avatar={avatar} open={editing} onOpenChange={setEditing} />

      <div className="relative aspect-[3/4] max-w-sm mx-auto rounded-2xl overflow-hidden bg-black border shadow-2xl">
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full object-cover bg-black" />
        <div className="absolute top-3 left-3">
          <StatusPill status={live.status} />
        </div>
        <button
          type="button"
          onClick={disconnected ? handleReconnect : handleDisconnect}
          className={`absolute top-3 right-3 flex items-center justify-center w-8 h-8 rounded-full backdrop-blur-md border transition-colors ${
            disconnected
              ? 'bg-emerald-500/80 hover:bg-emerald-500 text-white border-white/20'
              : 'bg-black/60 hover:bg-red-500/80 text-white/90 hover:text-white border-white/15'
          }`}
          aria-label={disconnected ? 'Reconnect' : 'Disconnect'}
          title={disconnected ? 'Reconnect' : 'Disconnect'}
        >
          <Power size={14} />
        </button>
      </div>

      {live.error && (
        <div className="max-w-sm mx-auto rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
          {live.error}
        </div>
      )}

      <form
        onSubmit={handleSendText}
        className="max-w-sm mx-auto flex items-center gap-2 rounded-2xl border bg-card p-2 shadow-xl"
      >
        <button
          type="button"
          onClick={toggleMute}
          disabled={live.status !== 'connected'}
          className={`flex items-center justify-center w-10 h-10 rounded-xl transition-colors disabled:opacity-40 ${
            muted ? 'bg-red-500/20 text-red-500' : 'bg-primary/15 text-primary hover:bg-primary/25'
          }`}
          aria-label={muted ? 'Unmute mic' : 'Mute mic'}
        >
          {muted ? <MicOff size={16} /> : <Mic size={16} />}
        </button>
        <Input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          placeholder={live.status === 'connected' ? 'Type to send · or just speak' : 'Connecting…'}
          disabled={live.status !== 'connected'}
          className="border-none bg-transparent shadow-none focus-visible:ring-0"
        />
        <Button type="submit" size="icon" disabled={live.status !== 'connected' || !textInput.trim()} className="rounded-xl">
          <Send size={16} />
        </Button>
      </form>
    </div>
  )
}

const STATUS_PILL: Record<AvatarLiveStatus, { label: string; cls: string; spin: boolean }> = {
  idle: { label: 'Idle', cls: 'bg-black/60 text-white', spin: false },
  connecting: { label: 'Connecting…', cls: 'bg-black/60 text-white', spin: true },
  connected: { label: 'Live', cls: 'bg-emerald-500/80 text-white', spin: false },
  error: { label: 'Error', cls: 'bg-red-500/80 text-white', spin: false },
  closed: { label: 'Disconnected', cls: 'bg-zinc-500/70 text-white', spin: false },
}

function StatusPill({ status }: { status: AvatarLiveStatus }) {
  const { label, cls, spin } = STATUS_PILL[status]
  return (
    <div
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium backdrop-blur-md border border-white/10 ${cls}`}
    >
      {spin && <Loader2 size={12} className="animate-spin" />}
      {label}
    </div>
  )
}
