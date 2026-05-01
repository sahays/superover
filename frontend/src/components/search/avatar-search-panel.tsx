// Avatar mode for /search. Owns the live session lifecycle and orchestrates
// the user's voice → search → spoken results loop.
//
// Two paths run simultaneously, with the tool-call path always preferred:
//
//   PRIMARY (tool calling): the backend declares a `search_movies` tool in
//   the setup frame for mode=search. The model decides when to call it,
//   emits a `toolCall` frame, and PAUSES until we send a `toolResponse` —
//   so the search and the narration can never race. The model then narrates
//   the result in one coherent response.
//
//   FALLBACK (transcript + single sendText): if the model never emits a
//   tool-call within the user-quiet window — e.g. because this preview
//   model doesn't honour functionDeclarations on the video modality — we
//   fire the search ourselves and inject one combined `clientContent` turn
//   asking the model to acknowledge + summarise in one response.
//
// `toolCallSeenRef` flips on the first tool-call event of the session and
// permanently disables the fallback for that session. Both paths share the
// `inFlightRef` lock so we can't double-fire.

import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Mic, MicOff, Power, User as UserIcon } from 'lucide-react'
import { searchApi } from '@/lib/api-client'
import { useAvatars } from '@/lib/api/avatars'
import { useAvatarLiveSession, type AvatarLiveStatus } from '@/hooks/useAvatarLiveSession'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { CuratedSearchResponse } from '@/types/search'

interface Props {
  // Pushed up so the parent can render result cards in the main column.
  onResults: (response: CuratedSearchResponse | null) => void
  onSearchingChange: (searching: boolean) => void
  onDuration: (seconds: number | null) => void
}

export function AvatarSearchPanel({ onResults, onSearchingChange, onDuration }: Props) {
  const { data: avatars, isLoading: loadingAvatars } = useAvatars()
  const avatarId = avatars?.[0]?.id ?? null

  const canvasRef = useRef<HTMLCanvasElement>(null)
  // Mic is off by default — click-to-talk. Without this the avatar's own
  // audio coming back through the speakers would feed into the mic and
  // get re-transcribed as a user query, kicking off another search.
  const [muted, setMuted] = useState(true)
  // Locks the speak button while a search round-trip is in flight. Cleared
  // when the search response returns; the user re-enables the mic by
  // clicking Speak again (still muted by default after that).
  const [searching, setSearching] = useState(false)
  // Warm-up gate. Status flips to 'connected' on setupComplete, but the
  // model needs a beat to be reliable about handling user audio. Without
  // this gate, clicking Speak immediately on connect produces a confused
  // model response (random greeting, no tool call).
  const [ready, setReady] = useState(false)
  // Latches when the user explicitly disconnects — stops the auto-start
  // effect inside useAvatarLiveSession from immediately reconnecting.
  const [disconnected, setDisconnected] = useState(false)
  const [latestUserText, setLatestUserText] = useState('')
  // Locks against the next search firing while the previous is in flight.
  // Without this, a user who keeps speaking can fan out parallel searches.
  const inFlightRef = useRef(false)
  // Latches true on the first tool-call event of this session. While true,
  // the fallback transcript path is dead — the model owns the trigger.
  const toolCallSeenRef = useRef(false)
  // Gemini Live emits `inputTranscription` events as either deltas or
  // cumulative text, and `finished` doesn't always arrive — so we buffer
  // until either isFinal hits or the user goes quiet for a beat. Used by
  // the fallback path only.
  const transcriptBufferRef = useRef('')
  const transcriptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Speculative search slot. Filled when the user mutes (turn ended) by
  // firing searchApi against the live transcript in parallel with the
  // model's ~2s VAD wait. The tool-call handler and the fallback path
  // await this promise before falling back to a fresh search — so a
  // tool-call that lands while the prefetch is still in flight reuses
  // it instead of fanning out into a parallel search.
  //
  // The query is the user's transcript (intent), not the model's possibly-
  // paraphrased tool-call query — but the curator handles paraphrase
  // translation server-side, so this is fine.
  const prefetchRef = useRef<{
    query: string
    promise: Promise<CuratedSearchResponse>
  } | null>(null)

  const live = useAvatarLiveSession({
    avatarId: avatarId ?? '',
    enabled: !!avatarId && !disconnected,
    canvasRef,
    mode: 'search',
  })

  // Apply the initial muted=true to AudioCapture as soon as it spins up.
  // Re-applies on every status change so we recover after teardown→reconnect.
  // Also resets toolCallSeenRef so the fallback path is re-armed across
  // session reboots — a single tool-call in a previous session shouldn't
  // permanently disable the fallback.
  useEffect(() => {
    if (live.status === 'connecting') {
      toolCallSeenRef.current = false
      prefetchRef.current = null
      setReady(false)
    }
    if (live.status === 'connected') {
      live.captureRef.current?.setMuted(muted)
      // 2-second warm-up. setupComplete arrives almost instantly but the
      // model isn't actually ready to handle user audio for ~1.5s after.
      const t = setTimeout(() => setReady(true), 2000)
      return () => clearTimeout(t)
    }
    setReady(false)
  }, [live.status, live.captureRef, muted])

  // Shared search runner. Returns a tuple [response | null, durationSec].
  // Mutes mic + flips local UI state up front; clears them in a finally.
  // The PRIMARY tool-call path uses this and sends a toolResponse on top.
  // The FALLBACK transcript path uses this and sends a combined sendText.
  const runSearch = async (
    rawQuery: string,
  ): Promise<[CuratedSearchResponse | null, number]> => {
    const query = rawQuery.trim()
    if (!query) return [null, 0]
    // Auto-mute: the avatar is about to narrate; without muting, that audio
    // would spill back into the mic and re-trigger.
    live.captureRef.current?.setMuted(true)
    setMuted(true)
    setSearching(true)
    onSearchingChange(true)
    onDuration(null)
    const start = performance.now()
    try {
      const response: CuratedSearchResponse = await searchApi.searchVideos(query, 20)
      const durationSec = Math.round((performance.now() - start) / 100) / 10
      onResults(response)
      onDuration(durationSec)
      // eslint-disable-next-line no-console
      console.log('[AvatarSearchPanel] search returned', {
        query,
        recommendations: response.recommendations.length,
        interpreted: response.interpreted_query,
      })
      return [response, durationSec]
    } finally {
      onSearchingChange(false)
      setSearching(false)
    }
  }

  // PRIMARY path — tool calling.
  // Model emits `tool-call` → we run the search → reply with `toolResponse`.
  // The model is paused while waiting for the response, then narrates the
  // result naturally as a single coherent spoken turn. No race, no bookend.
  useEffect(() => {
    const session = live.sessionRef.current
    if (!session) return

    const handler = async (e: Event) => {
      const detail = (e as CustomEvent).detail as {
        id: string
        name: string
        args: Record<string, unknown>
      }
      if (detail.name !== 'search_movies') return
      // eslint-disable-next-line no-console
      console.log('[AvatarSearchPanel] tool-call', detail)
      toolCallSeenRef.current = true
      // Cancel any pending fallback timer — the primary path owns this turn.
      if (transcriptTimerRef.current) {
        clearTimeout(transcriptTimerRef.current)
        transcriptTimerRef.current = null
      }
      transcriptBufferRef.current = ''

      // Fast path: speculative search fired on mute. Await the promise
      // (which may already be resolved, or still in flight). Saves the
      // ~1s tool-round-trip and the avatar starts narrating immediately.
      // We trust the user's transcript over the model's possibly-paraphrased
      // tool-call query; the curator handles paraphrase translation
      // server-side.
      const cached = prefetchRef.current
      if (cached) {
        prefetchRef.current = null
        try {
          const response = await cached.promise
          session.sendToolResponse(detail.id, detail.name, {
            summary: response.response_text || 'No matching results were found.',
            result_count: response.recommendations.length,
            interpreted_query: response.interpreted_query,
          })
          // eslint-disable-next-line no-console
          console.log('[AvatarSearchPanel] tool returned (prefetched)', {
            result_count: response.recommendations.length,
          })
          return
        } catch (err) {
          session.sendToolResponse(detail.id, detail.name, {
            error: err instanceof Error ? err.message : 'search failed',
          })
          // eslint-disable-next-line no-console
          console.error('[AvatarSearchPanel] prefetched search failed', err)
          return
        }
      }

      if (inFlightRef.current) {
        // Another search path snuck in. Tell the model so it doesn't wait.
        session.sendToolResponse(detail.id, detail.name, {
          error: 'a search is already in progress',
        })
        return
      }
      inFlightRef.current = true

      const query = String(detail.args.query ?? '').trim()
      if (!query) {
        session.sendToolResponse(detail.id, detail.name, { error: 'empty query' })
        inFlightRef.current = false
        return
      }
      try {
        const [response] = await runSearch(query)
        if (!response) {
          session.sendToolResponse(detail.id, detail.name, { result_count: 0 })
          return
        }
        session.sendToolResponse(detail.id, detail.name, {
          summary: response.response_text || 'No matching results were found.',
          result_count: response.recommendations.length,
          interpreted_query: response.interpreted_query,
        })
        // eslint-disable-next-line no-console
        console.log('[AvatarSearchPanel] tool returned', {
          result_count: response.recommendations.length,
        })
      } catch (err) {
        session.sendToolResponse(detail.id, detail.name, {
          error: err instanceof Error ? err.message : 'search failed',
        })
        // eslint-disable-next-line no-console
        console.error('[AvatarSearchPanel] tool search failed', err)
      } finally {
        inFlightRef.current = false
      }
    }

    session.addEventListener('tool-call', handler)
    return () => session.removeEventListener('tool-call', handler)
  }, [live.status, live.sessionRef, onResults, onSearchingChange, onDuration])

  // FALLBACK path — transcript + quiet timeout + single combined sendText.
  // Only fires if no tool-call has been seen this session. Identical to the
  // pre-tool-calling shipped behaviour.
  useEffect(() => {
    const session = live.sessionRef.current
    if (!session) return

    const fireFallback = async (raw: string) => {
      if (toolCallSeenRef.current || inFlightRef.current) return
      const text = raw.trim()
      if (!text) return
      inFlightRef.current = true
      transcriptBufferRef.current = ''
      // eslint-disable-next-line no-console
      console.log('[AvatarSearchPanel] fallback: no tool-call seen, firing manual search for:', text)
      try {
        // Prefer the prefetched promise if one was fired on mute — same
        // turn, same query, no need to round-trip again.
        const cached = prefetchRef.current
        let response: CuratedSearchResponse | null
        if (cached) {
          prefetchRef.current = null
          try {
            response = await cached.promise
          } catch {
            const [r] = await runSearch(text)
            response = r
          }
        } else {
          const [r] = await runSearch(text)
          response = r
        }
        const summary = response?.response_text || 'No matching results were found.'
        // Single combined turn — see comment in plan: two separate turns race.
        session.sendText(
          `The user just asked: "${text}".\n\n` +
            `[SEARCH_RESULTS]\n${summary}\n\n` +
            'Reply in this exact order, as one continuous spoken response:\n' +
            '1. A brief acknowledgment ("Here\'s what I found…" or similar — one short clause).\n' +
            '2. A 1-2 sentence summary of the results above.\n' +
            'Stay grounded in the [SEARCH_RESULTS] text. Do not invent details. ' +
            'Do not name films, actors, or scenes that are not in the [SEARCH_RESULTS] payload.',
        )
      } catch (err) {
        session.sendText(
          'Tell the user the search hit an error and ask them to try again, in one short sentence.',
        )
        // eslint-disable-next-line no-console
        console.error('[AvatarSearchPanel] fallback search failed', err)
      } finally {
        inFlightRef.current = false
      }
    }

    const scheduleQuietTrigger = () => {
      if (transcriptTimerRef.current) clearTimeout(transcriptTimerRef.current)
      transcriptTimerRef.current = setTimeout(() => {
        if (toolCallSeenRef.current) return
        const buf = transcriptBufferRef.current
        if (buf.trim()) void fireFallback(buf)
      }, 900)
    }

    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as {
        role: 'user' | 'model'
        text: string
        isFinal: boolean
      }
      if (detail.role !== 'user') return
      // Even if the primary path will end up handling this, we still update
      // the user-facing transcript caption here.
      const incoming = detail.text
      const buf = transcriptBufferRef.current
      transcriptBufferRef.current = incoming.startsWith(buf)
        ? incoming
        : (buf + incoming).trim()
      const merged = transcriptBufferRef.current.trim()
      if (merged) setLatestUserText(merged)
      if (toolCallSeenRef.current) return
      if (detail.isFinal && merged) {
        if (transcriptTimerRef.current) clearTimeout(transcriptTimerRef.current)
        void fireFallback(merged)
        return
      }
      scheduleQuietTrigger()
    }

    session.addEventListener('transcript', handler)
    return () => {
      session.removeEventListener('transcript', handler)
      if (transcriptTimerRef.current) clearTimeout(transcriptTimerRef.current)
    }
  }, [live.status, live.sessionRef, onResults, onSearchingChange, onDuration])

  const handleDisconnect = () => {
    live.teardown()
    live.setStatus('closed')
    setDisconnected(true)
  }

  const handleReconnect = () => {
    live.setError(null)
    setDisconnected(false)
  }

  const toggleMute = () => {
    if (!ready || searching) return
    const next = !muted
    setMuted(next)
    live.captureRef.current?.setMuted(next)
    void live.sinkRef.current?.resume()
    void live.audioPlayerRef.current?.resume()

    if (next === false) {
      // Going from muted → listening: a new turn is starting. Drop any stale
      // prefetch from a prior turn so it can't bleed into this one's response.
      prefetchRef.current = null
      return
    }

    // Going from listening → muted: speculative prefetch using whatever the
    // live transcription has captured. Runs in parallel with the model's VAD
    // wait + tool-call decision; the result is consumed by either the
    // tool-call handler or the fallback path. Cards render optimistically
    // when the prefetch resolves, ~1s ahead of the avatar's narration.
    const text = transcriptBufferRef.current.trim()
    if (!text || prefetchRef.current || inFlightRef.current) return

    setSearching(true)
    onSearchingChange(true)
    onDuration(null)
    const startTime = performance.now()
    // eslint-disable-next-line no-console
    console.log('[AvatarSearchPanel] prefetch firing for:', text)
    const promise = searchApi.searchVideos(text, 20) as Promise<CuratedSearchResponse>
    prefetchRef.current = { query: text, promise }
    promise
      .then((response) => {
        // Optimistic UI: cards land before the avatar starts narrating.
        onResults(response)
        onDuration(Math.round((performance.now() - startTime) / 100) / 10)
        // eslint-disable-next-line no-console
        console.log('[AvatarSearchPanel] prefetch resolved', {
          recommendations: response.recommendations.length,
        })
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.error('[AvatarSearchPanel] prefetch failed', err)
      })
      .finally(() => {
        setSearching(false)
        onSearchingChange(false)
      })
  }

  if (loadingAvatars) {
    return (
      <Card className="w-72">
        <CardContent className="p-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading avatar…
        </CardContent>
      </Card>
    )
  }

  if (!avatarId) {
    return (
      <Card className="w-72">
        <CardContent className="p-4 text-sm space-y-2">
          <div className="flex items-center gap-2 text-muted-foreground">
            <UserIcon className="h-4 w-4" /> No avatar configured
          </div>
          <Link to="/avatars/create" className="text-primary hover:underline">
            Create one to enable Avatar mode →
          </Link>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-72 overflow-hidden shadow-lg">
      <div className="relative aspect-[3/4] bg-black">
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full object-cover bg-black" />
        <div className="absolute top-2 left-2">
          <StatusPill status={live.status} />
        </div>
        <button
          type="button"
          onClick={disconnected ? handleReconnect : handleDisconnect}
          className={`absolute top-2 right-2 flex items-center justify-center w-7 h-7 rounded-full backdrop-blur-md border transition-colors ${
            disconnected
              ? 'bg-emerald-500/80 hover:bg-emerald-500 text-white border-white/20'
              : 'bg-black/60 hover:bg-red-500/80 text-white/90 hover:text-white border-white/15'
          }`}
          aria-label={disconnected ? 'Reconnect' : 'Disconnect'}
          title={disconnected ? 'Reconnect' : 'Disconnect'}
        >
          <Power size={12} />
        </button>
      </div>

      <CardContent className="p-3 space-y-2">
        {live.error && <p className="text-xs text-destructive">{live.error}</p>}
        {latestUserText && (
          <p className="text-xs text-muted-foreground italic line-clamp-2">
            “{latestUserText}”
          </p>
        )}
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={searching ? 'secondary' : muted ? 'default' : 'destructive'}
            onClick={toggleMute}
            disabled={!ready || searching}
            className="flex-1"
            title={
              !ready
                ? 'Avatar warming up…'
                : searching
                  ? 'Searching — please wait'
                  : muted
                    ? 'Click and speak'
                    : 'Click to stop listening'
            }
          >
            {!ready ? (
              <>
                <Loader2 size={14} className="mr-1.5 animate-spin" /> Warming up…
              </>
            ) : searching ? (
              <>
                <Loader2 size={14} className="mr-1.5 animate-spin" /> Searching…
              </>
            ) : muted ? (
              <>
                <Mic size={14} className="mr-1.5" /> Click to speak
              </>
            ) : (
              <>
                <MicOff size={14} className="mr-1.5" /> Listening… (click to stop)
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
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
      className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium backdrop-blur-md border border-white/10 ${cls}`}
    >
      {spin && <Loader2 size={10} className="animate-spin" />}
      {label}
    </div>
  )
}
