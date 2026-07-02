// Avatar mode for /search. Owns the live session lifecycle and an
// event-driven search pipeline (no ack phase, no filler — the search
// backend answers in ~0.3s):
//
//   1. user speaks; pause (AUTO_STOP_MS) auto-triggers pipeline
//   2. panel shows "You asked: <transcript>"            (immediate)
//   3. searchApi(transcript) fires; cards render in the main column the
//      moment it resolves
//   4. panel sends sendText("[SEARCH_RESULTS] …") right away → avatar
//      narrates; if the model's VAD micro-ack ("One moment!") is still
//      generating, the narration turn interrupts it — by design
//
// Pipeline state is a small finite-state machine driven via useReducer. The
// reducer is pure; side effects (sendText, searchApi, mic mute) run in
// useEffect hooks keyed off the state. Mic muted is *derived* from state —
// the mic is open iff state.kind === 'listening'.
//
// State-machine diagram:
//
//                    +-----------+   click   +-----------+
//                    |   idle    |---------->| listening |
//                    +-----------+           +-----------+
//                          ^                   |        |
//                          |          stop +empty       | stop +text
//             narration-sent|         transcript        |
//                          |                  |         v
//                          |                  |    +---------+
//                          |                  +----|         |
//                          |                       | asking  |
//                          |   search-resolved     |         |
//                          |       +---------------+---------+
//                          |       |
//                          |       v
//                          |  +---------------+
//                          +--+  summarising  |
//                             +---------------+
//
// Connection-side state (live.status, ready warm-up, disconnected) lives
// outside this FSM since it's owned by useAvatarLiveSession. The FSM only
// covers what the panel does once we're connected + ready.

import { useEffect, useReducer, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Mic, MicOff, Power, User as UserIcon } from 'lucide-react'
import { searchApi } from '@/lib/api-client'
import { useAvatars } from '@/lib/api/avatars'
import { useAvatarLiveSession, type AvatarLiveStatus } from '@/hooks/useAvatarLiveSession'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { CuratedSearchResponse } from '@/types/search'

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type PipelineState =
  | { kind: 'idle'; lastQuery: string }
  | { kind: 'listening'; transcript: string }
  | { kind: 'asking'; query: string }
  | { kind: 'summarising'; query: string }

type PipelineEvent =
  | { type: 'mic-on' }
  | { type: 'mic-off-empty' }
  | { type: 'pipeline-start'; query: string }
  | { type: 'transcript-update'; text: string }
  | { type: 'search-resolved' }
  | { type: 'narration-sent' }
  | { type: 'reset' }

const INITIAL_STATE: PipelineState = { kind: 'idle', lastQuery: '' }

function pipelineReducer(state: PipelineState, event: PipelineEvent): PipelineState {
  switch (event.type) {
    case 'mic-on':
      if (state.kind === 'idle') return { kind: 'listening', transcript: '' }
      return state
    case 'transcript-update':
      // Accumulate only while listening; ignore stale transcript events that
      // arrive after the user has clicked stop (Gemini Live can lag the
      // transcription by a few hundred ms).
      if (state.kind === 'listening') return { ...state, transcript: event.text }
      return state
    case 'mic-off-empty':
      if (state.kind === 'listening') return { kind: 'idle', lastQuery: '' }
      return state
    case 'pipeline-start':
      if (state.kind === 'listening') return { kind: 'asking', query: event.query }
      return state
    case 'search-resolved':
      if (state.kind === 'asking') return { kind: 'summarising', query: state.query }
      return state
    case 'narration-sent':
      if (state.kind === 'summarising' || state.kind === 'asking') {
        return { kind: 'idle', lastQuery: state.query }
      }
      return state
    case 'reset':
      return INITIAL_STATE
  }
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// User-pause threshold. We dispatch pipeline-start automatically when no
// new transcript chunk has arrived for this long while in `listening`.
// Within-sentence pauses are typically 200-400ms; between-sentence pauses
// up to ~800ms. 900ms clears both while keeping the pre-search dead time
// short — with the backend at ~0.3s this window dominates perceived latency.
const AUTO_STOP_MS = 900

// Warm-up after `setupComplete` — the model is briefly unreliable about
// handling user audio in the first ~1.5s.
const WARM_UP_MS = 2000

// Pure safety net for a DROPPED `turn-complete`. End-of-turn is normally driven
// by the authoritative `turn-complete` + audio-drain (see waitForModelSpeechEnd),
// never by this cap — so it's set generously and can't clip a real utterance.
// Results render independently of speech, so it never delays what the user sees.
const SPEECH_HARD_CAP_MS = 15000

// Tiny buffer added after the WebAudio queue is supposed to have drained.
// Covers slop between AudioContext clock and AudioBufferSourceNode's actual
// stop time, plus a small "natural pause" before the next utterance.
const PLAYBACK_TAIL_MS = 200

// Ignore turn-completes arriving sooner than this after the narration is
// sent: the interrupted micro-ack's turn-complete can land just after the
// send, and treating it as narration-end would idle the panel mid-speech.
// Real narration turn-completes arrive only after all its audio is
// delivered (several seconds for a 5-item summary).
const NARRATION_MIN_TURN_MS = 1500

// Build the [SEARCH_RESULTS] narration payload from the structured
// recommendations. The backend no longer writes narration prose (the curator
// LLM was removed for latency); the Live model composes the spoken summary
// from this list, judging relevance itself per the search-mode overlay.
function buildSearchResultsPayload(response: CuratedSearchResponse): string {
  const all = response.recommendations ?? []
  // Narrate only the meaningful tiers — the loose "also_like" tail is for
  // browsing on screen, not for the avatar to read out.
  const strong = all.filter((r) => (r.tier ?? 'best') !== 'also_like')
  const recs = (strong.length > 0 ? strong : all).slice(0, 5)
  if (recs.length === 0) return '[SEARCH_RESULTS]\nNo matches found.'
  const lines = recs.map((rec, i) => {
    const clip =
      rec.recommendation_type === 'clip' && rec.clip_start && rec.clip_end
        ? ` (clip ${rec.clip_start}-${rec.clip_end})`
        : ''
    return `${i + 1}. "${rec.title}"${clip} — ${rec.reason} [confidence ${rec.confidence.toFixed(2)}]`
  })
  return `[SEARCH_RESULTS]\n${recs.length} match(es):\n${lines.join('\n')}`
}

// Resolves once the model's turn has fully ENDED and the local audio has
// drained — driven by authoritative signals, with no mid-utterance guesswork:
//   1. first audio chunk arrives — guards against a stale `turn-complete` that
//      fires before the model actually starts speaking (e.g. from closing the
//      user's input turn)
//   2. `turn-complete` — the model declares the turn done. Per the transport it
//      fires only AFTER all audio for the turn has been delivered to the local
//      queue, so it never arrives mid-utterance
//   3. drain the local WebAudio buffer (`getAudioRemainingMs`) so playback
//      finishes before the caller sends the next turn (this is what prevents
//      barge-in / clipping)
// `hardCapMs` is a PURE safety net for a dropped `turn-complete` — never the
// normal path — so it can't clip a real utterance early.
//
// Used for turns WE initiate (filler, summary): we attach the listeners before
// `sendText`, so the response's audio + `turn-complete` are reliably observed.
// For a turn we did NOT initiate (the VAD auto-ack, which can finish before we
// attach), use `waitForModelIdle` instead.
async function waitForModelSpeechEnd(
  session: {
    addEventListener: (t: string, h: () => void) => void
    removeEventListener: (t: string, h: () => void) => void
  },
  getAudioRemainingMs: () => number,
  opts: { hardCapMs?: number; minTurnMs?: number } = {},
): Promise<void> {
  const hardCapMs = opts.hardCapMs ?? SPEECH_HARD_CAP_MS
  const minTurnMs = opts.minTurnMs ?? 0
  const startedAt = Date.now()
  // Phase 1: wait for first audio chunk, then `turn-complete` (or the safety cap).
  await new Promise<void>((resolve) => {
    let heardMedia = false
    let done = false
    let hardTimer: ReturnType<typeof setTimeout> | null = null
    const finish = () => {
      if (done) return
      done = true
      session.removeEventListener('turn-complete', onTurnComplete)
      session.removeEventListener('audio-chunk', onMedia)
      session.removeEventListener('video-chunk', onMedia)
      if (hardTimer) clearTimeout(hardTimer)
      resolve()
    }
    // Audio-only mode delivers audio-chunk; video mode delivers video-chunk
    // (audio muxed inside the MP4). Either counts as "the model is speaking".
    const onMedia = () => {
      heardMedia = true
    }
    const onTurnComplete = () => {
      if (heardMedia && Date.now() - startedAt >= minTurnMs) finish()
    }
    session.addEventListener('audio-chunk', onMedia)
    session.addEventListener('video-chunk', onMedia)
    session.addEventListener('turn-complete', onTurnComplete)
    hardTimer = setTimeout(finish, hardCapMs)
  })
  // Phase 2: drain the local audio queue. Because `turn-complete` fires only
  // after all audio is delivered, the queue already holds the whole utterance,
  // so a single computed wait drains it exactly. Bounded by the cap budget.
  const budget = Math.max(0, hardCapMs - (Date.now() - startedAt))
  const remaining = Math.min(getAudioRemainingMs(), budget)
  if (remaining > 0) {
    await new Promise((r) => setTimeout(r, remaining + PLAYBACK_TAIL_MS))
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  /** Currently selected avatar id (typically driven by `?avatar=<id>` URL param). */
  avatarId?: string | null
  /** Called when the panel auto-selects or the user picks an avatar. */
  onSelectAvatar?: (id: string) => void
  onResults: (response: CuratedSearchResponse | null) => void
  onSearchingChange: (searching: boolean) => void
  onDuration: (seconds: number | null) => void
}

export function AvatarSearchPanel({
  avatarId: avatarIdProp,
  onSelectAvatar,
  onResults,
  onSearchingChange,
  onDuration,
}: Props) {
  const { data: avatars, isLoading: loadingAvatars } = useAvatars()
  // Resolve the active avatar:
  //   1. if the parent supplied a valid id, use it
  //   2. else if exactly one avatar exists, auto-select it (notify parent)
  //   3. else (>1 avatar, none selected) leave null → picker UI renders
  const validProvided =
    avatarIdProp && avatars?.some((a) => a.id === avatarIdProp) ? avatarIdProp : null
  const avatarId =
    validProvided ?? (avatars && avatars.length === 1 ? avatars[0].id : null)
  // Push an auto-selected single-avatar id back up to the parent so the URL
  // stays in sync. Effect runs once per resolution change.
  useEffect(() => {
    if (!validProvided && avatarId && onSelectAvatar) {
      onSelectAvatar(avatarId)
    }
  }, [validProvided, avatarId, onSelectAvatar])

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [state, dispatch] = useReducer(pipelineReducer, INITIAL_STATE)
  const [ready, setReady] = useState(false)
  const [disconnected, setDisconnected] = useState(false)

  // Refs the side effects need outside the reducer.
  const transcriptBufferRef = useRef('')
  // Auto-stop timer: while listening, each new transcript chunk resets it.
  // When it fires (no chunk for AUTO_STOP_MS), we treat it as end-of-speech
  // and kick off the pipeline.
  const autoStopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Mirrors `state.kind` synchronously so event handlers (which capture the
  // initial closure) can read the current state.
  const stateKindRef = useRef<PipelineState['kind']>(state.kind)
  useEffect(() => {
    stateKindRef.current = state.kind
  }, [state.kind])
  // Stable ref to runPipeline so the transcript handler closure always
  // sees the latest version without re-binding the listener.
  const runPipelineRef = useRef<(query: string) => Promise<void>>(async () => {})
  const live = useAvatarLiveSession({
    avatarId: avatarId ?? '',
    enabled: !!avatarId && !disconnected,
    canvasRef,
    mode: 'search',
  })

  // Mic is muted iff we are NOT in 'listening'. Single source of truth.
  const muted = state.kind !== 'listening'
  const isWorking = state.kind === 'asking' || state.kind === 'summarising'

  // Surface "searching" upward so the parent can disable its own affordances.
  useEffect(() => {
    onSearchingChange(isWorking)
  }, [isWorking, onSearchingChange])

  // Sync the mic to the FSM. Anything other than `listening` mutes it.
  // Re-fire on `live.status` so the desired mute state is applied as soon
  // as the capture exists — the capture is created inside the connect
  // effect, after this component has already mounted, so without the
  // status dep an initial idle→muted transition would no-op against a
  // null captureRef and never re-run.
  useEffect(() => {
    live.captureRef.current?.setMuted(muted)
  }, [muted, live.captureRef, live.status])

  // Connection lifecycle: reset FSM and warm-up gate when the session
  // (re)connects.
  useEffect(() => {
    if (live.status === 'connecting') {
      setReady(false)
      transcriptBufferRef.current = ''
      if (autoStopTimerRef.current) {
        clearTimeout(autoStopTimerRef.current)
        autoStopTimerRef.current = null
      }
      dispatch({ type: 'reset' })
    }
    if (live.status === 'connected') {
      const t = setTimeout(() => setReady(true), WARM_UP_MS)
      return () => clearTimeout(t)
    }
    setReady(false)
  }, [live.status])

  // Cancel any pending auto-stop timer when we leave the listening state.
  useEffect(() => {
    if (state.kind !== 'listening' && autoStopTimerRef.current) {
      clearTimeout(autoStopTimerRef.current)
      autoStopTimerRef.current = null
    }
  }, [state.kind])

  // Listen for user input transcription so the FSM has live transcript
  // text to consume on click-stop.
  useEffect(() => {
    const session = live.sessionRef.current
    if (!session) return
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as {
        role: 'user' | 'model'
        text: string
      }
      if (detail.role !== 'user') return
      // Cumulative-vs-delta heuristic — Gemini Live sends either depending
      // on the build. We end up with the longest coherent prefix.
      const incoming = detail.text
      const buf = transcriptBufferRef.current
      transcriptBufferRef.current = incoming.startsWith(buf)
        ? incoming
        : (buf + incoming).trim()
      const merged = transcriptBufferRef.current.trim()
      // Only push into FSM state during listening; otherwise the late
      // transcript would mutate the displayed query mid-pipeline.
      if (stateKindRef.current === 'listening' && merged) {
        dispatch({ type: 'transcript-update', text: merged })
        // Reset auto-stop. Pipeline kicks off when no new chunk arrives
        // for AUTO_STOP_MS — i.e., the user has paused.
        if (autoStopTimerRef.current) clearTimeout(autoStopTimerRef.current)
        autoStopTimerRef.current = setTimeout(() => {
          autoStopTimerRef.current = null
          if (stateKindRef.current !== 'listening') return
          const finalQuery = transcriptBufferRef.current.trim()
          if (!finalQuery) return
          dispatch({ type: 'pipeline-start', query: finalQuery })
          void runPipelineRef.current(finalQuery)
        }, AUTO_STOP_MS)
      }
    }
    session.addEventListener('transcript', handler)
    return () => session.removeEventListener('transcript', handler)
  }, [live.status, live.sessionRef])

  // Event-driven pipeline. The search backend answers in ~0.2-0.5s, so there
  // is no ack phase and no small talk: the overlay caps the model's automatic
  // VAD response to a couple of words (or silence) and the narration is sent
  // as soon as that response has GENERATED (its audio may still be playing —
  // narration audio queues behind it, so speech is continuous, never clipped).
  //
  // Sequence:
  //   1. fire searchApi(query) immediately; cards render the moment it resolves
  //   2. await the auto-response's generation completing (not its playback)
  //   3. await the search (already resolved in practice), FSM → summarising
  //   4. sendText([SEARCH_RESULTS] …); await the narration finishing
  const runPipeline = async (query: string) => {
    const session = live.sessionRef.current
    if (!session) return
    onDuration(null)

    // Per-step latency tracing for the avatar pipeline. The search sub-steps
    // (interpret/bq/curate) are logged server-side in Cloud Run; everything
    // here (ack / filler / narration speech) is client-orchestrated, so we
    // trace it in the browser console with elapsed-since-start timestamps.
    const t0 = performance.now()
    const elapsed = () => Math.round(performance.now() - t0)
    const log = (msg: string, extra?: Record<string, unknown>) => {
      // eslint-disable-next-line no-console
      console.log(`[AvatarPipeline +${elapsed()}ms] ${msg}`, extra ?? '')
    }
    log('start', { query })

    const remainingMs = () => live.sinkRef.current?.audioRemainingMs() ?? 0

    try {
      // Step 1: fire the search IMMEDIATELY. The moment it resolves we render
      // the cards and report the REAL end-to-end wait (pipeline start → results)
      // — independently of what the avatar is saying, so results are never
      // gated behind a speech turn, and the on-screen time reflects reality.
      const startTime = performance.now()
      log('search: fired')
      const searchPromise: Promise<CuratedSearchResponse | null> = (
        searchApi.searchVideos(query, 20) as Promise<CuratedSearchResponse>
      ).catch(() => null)
      void searchPromise.then((r) => {
        if (r) {
          onResults(r)
          // Displayed duration counts from when the user actually stopped
          // speaking: the pipeline starts AUTO_STOP_MS after the last
          // transcript chunk, so add that window back in. Keeps the badge
          // honest against perceived wait.
          onDuration(Math.round((elapsed() + AUTO_STOP_MS) / 100) / 10)
        }
        log('search: resolved', {
          e2eMs: elapsed(),
          searchMs: Math.round(performance.now() - startTime),
          recs: r?.recommendations?.length ?? 0,
        })
      })

      // Step 2: there is NO ack wait. The model's VAD auto-response (capped
      // at "One moment!"/silence by the overlay) is disposable: sending the
      // narration turn while it is still generating simply interrupts it,
      // and losing half of a two-word ack is imperceptible. There is no
      // reliable end-of-ack signal to wait on anyway — in video mode the
      // avatar streams idle-animation frames continuously, so media-recency
      // heuristics never settle (this previously burned an 8s timeout cap
      // on every query).
      const response = await searchPromise
      log('cards: rendered', { e2eMs: elapsed(), ok: !!response })
      dispatch({ type: 'search-resolved' })

      // Step 3: summary (or apology if search failed) — sent immediately.
      // Wait for it to finish playing so the panel returns to idle in
      // lockstep with the avatar going quiet. `minTurnMs` ignores a stray
      // turn-complete from the interrupted ack landing right after send.
      const summaryStart = performance.now()
      log('summary: sending')
      const summaryDone = waitForModelSpeechEnd(session, remainingMs, {
        minTurnMs: NARRATION_MIN_TURN_MS,
      })
      if (!response) {
        session.sendText(
          'Tell the user the search hit an error and ask them to try again, in one short sentence.',
        )
      } else {
        session.sendText(
          `${buildSearchResultsPayload(response)}\n\n` +
            'Explain the best matches to the user in 2-3 short spoken sentences, in your ' +
            'usual voice and personality. Open with a brief natural lead-in (e.g. ' +
            '"Alright — here\'s what I found") so it flows smoothly from whatever you ' +
            'were just saying. Stay grounded entirely in the [SEARCH_RESULTS] ' +
            'list. Do not name any film, actor, or scene that is not in it.',
        )
      }
      await summaryDone
      log('summary: spoken', { ms: Math.round(performance.now() - summaryStart) })
    } finally {
      log('done', { totalMs: elapsed() })
      // Reset every per-query ref so the next pipeline starts clean.
      transcriptBufferRef.current = ''
      if (autoStopTimerRef.current) {
        clearTimeout(autoStopTimerRef.current)
        autoStopTimerRef.current = null
      }
      dispatch({ type: 'narration-sent' })
    }
  }

  // Always have a fresh runPipeline reference for the auto-stop closure.
  useEffect(() => {
    runPipelineRef.current = runPipeline
  })

  const handleSpeakClick = () => {
    if (live.status !== 'connected' || !ready) return
    // Listening transitions out automatically on pause (1.2s of no new
    // transcript chunks), so the only click we honour is idle → listening.
    if (state.kind !== 'idle') return
    transcriptBufferRef.current = ''
    dispatch({ type: 'mic-on' })
    // Kick the audio sinks so browser autoplay policy lets them play.
    void live.sinkRef.current?.resume()
    void live.audioPlayerRef.current?.resume()
  }

  const handleDisconnect = () => {
    live.teardown()
    live.setStatus('closed')
    setDisconnected(true)
  }

  const handleReconnect = () => {
    live.setError(null)
    setDisconnected(false)
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
    // No avatar selected. Either zero avatars exist (offer to create one)
    // or multiple exist and none was picked yet (show picker).
    if (!avatars || avatars.length === 0) {
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
      <Card className="w-72">
        <CardContent className="p-4 text-sm space-y-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <UserIcon className="h-4 w-4" /> Pick an avatar
          </div>
          <div className="space-y-1.5">
            {avatars.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => onSelectAvatar?.(a.id)}
                className="w-full text-left px-3 py-2 rounded-md border border-muted-foreground/20 hover:border-primary/50 hover:bg-accent transition-colors"
              >
                <div className="font-medium">{a.name}</div>
                <div className="text-xs text-muted-foreground capitalize">
                  {a.style.replace(/_/g, ' ')} · {a.voice}
                </div>
              </button>
            ))}
          </div>
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
        <PipelineStatus state={state} ready={ready} liveStatus={live.status} />
        <SpeakButton
          state={state}
          ready={ready}
          liveStatus={live.status}
          muted={muted}
          onClick={handleSpeakClick}
        />
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function PipelineStatus({
  state,
  ready,
  liveStatus,
}: {
  state: PipelineState
  ready: boolean
  liveStatus: AvatarLiveStatus
}) {
  if (liveStatus !== 'connected' || !ready) return null

  // Only show the user-facing transcript / last query as a caption.
  // Phase status (Searching… / Narrating…) is owned by the button, so we
  // don't repeat it here.
  let text = ''
  switch (state.kind) {
    case 'idle':
      text = state.lastQuery
      break
    case 'listening':
      text = state.transcript
      break
    case 'asking':
    case 'summarising':
      text = state.query
      break
  }
  if (!text) return null
  return <p className="text-xs text-muted-foreground italic line-clamp-3">“{text}”</p>
}

function SpeakButton({
  state,
  ready,
  liveStatus,
  muted,
  onClick,
}: {
  state: PipelineState
  ready: boolean
  liveStatus: AvatarLiveStatus
  muted: boolean
  onClick: () => void
}) {
  const isWorking = state.kind === 'asking' || state.kind === 'summarising'
  // Button is now an idle-only action: clicking it starts listening; pause
  // detection auto-transitions out. So once we're past idle, it's disabled.
  const disabled = liveStatus !== 'connected' || !ready || state.kind !== 'idle'

  let label: React.ReactNode
  let title: string
  if (liveStatus === 'closed' || liveStatus === 'error') {
    // Disconnected (or errored) — reconnect is via the power button, so the
    // speak button is just an inert status here, not "warming up".
    label = (
      <>
        <Power size={14} className="mr-1.5" /> Disconnected
      </>
    )
    title = 'Disconnected — use the power button to reconnect'
  } else if (!ready || liveStatus !== 'connected') {
    label = (
      <>
        <Loader2 size={14} className="mr-1.5 animate-spin" /> Warming up…
      </>
    )
    title = 'Avatar warming up…'
  } else if (state.kind === 'asking') {
    label = (
      <>
        <Loader2 size={14} className="mr-1.5 animate-spin" /> Searching…
      </>
    )
    title = 'Searching — please wait'
  } else if (state.kind === 'summarising') {
    label = (
      <>
        <Loader2 size={14} className="mr-1.5 animate-spin" /> Narrating results…
      </>
    )
    title = 'Avatar narrating results — please wait'
  } else if (state.kind === 'listening') {
    label = (
      <>
        <MicOff size={14} className="mr-1.5" /> Listening… (pause to send)
      </>
    )
    title = 'Stop talking for ~1 s to auto-send'
  } else {
    // idle
    label = (
      <>
        <Mic size={14} className="mr-1.5" /> Click to speak
      </>
    )
    title = 'Click and speak'
  }

  return (
    <Button
      type="button"
      size="sm"
      variant={isWorking ? 'secondary' : muted ? 'default' : 'destructive'}
      onClick={onClick}
      disabled={disabled}
      className="flex-1 w-full"
      title={title}
    >
      {label}
    </Button>
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
