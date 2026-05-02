/* eslint-disable no-empty -- silent on JSON parse / send-after-close races */
// WebSocket client for the v2 live session. Connects to our backend's proxy
// endpoint (which terminates the upstream Vertex AI Gemini Live socket using
// service-account credentials), then relays/parses Gemini Live frames.
//
// The browser never sees an access token — the proxy is the only thing that
// authenticates with Vertex AI.

export type LiveMessage =
  | { type: 'connected' }
  | { type: 'disconnected'; code: number; reason: string }
  | { type: 'video-chunk'; mimeType: string; data: Uint8Array }
  | { type: 'audio-chunk'; mimeType: string; data: Uint8Array }
  | { type: 'transcript'; role: 'user' | 'model'; text: string; isFinal: boolean }
  | {
      type: 'tool-call'
      id: string
      name: string
      args: Record<string, unknown>
    }
  | { type: 'turn-complete' }
  | { type: 'error'; error: Error }

export class GeminiLiveSession extends EventTarget {
  private ws: WebSocket | null = null
  private connected = false

  /**
   * Open the WS connection. Resolves when the upstream `setupComplete` frame
   * arrives, rejects on socket close before then.
   */
  connect(url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url)
      ws.binaryType = 'arraybuffer'
      this.ws = ws

      let settled = false
      const settle = (fn: () => void) => {
        if (!settled) {
          settled = true
          fn()
        }
      }

      ws.onopen = () => {
        // The backend sends the upstream `setup` frame on our behalf, so we
        // wait for setupComplete before declaring "connected".
      }
      ws.onmessage = (e) => this._handleMessage(e.data, () => settle(resolve))
      ws.onerror = () => {
        const err = new Error('WebSocket error')
        this._dispatch({ type: 'error', error: err })
        settle(() => reject(err))
      }
      ws.onclose = (e) => {
        this.connected = false
        this._dispatch({ type: 'disconnected', code: e.code, reason: e.reason })
        settle(() => reject(new Error(`WebSocket closed: ${e.code} ${e.reason}`)))
      }
    })
  }

  sendText(text: string) {
    // clientContent + turnComplete:true closes the user turn explicitly so
    // the model responds NOW. realtimeInput.text (the prior approach) keeps
    // the turn open and waits for VAD silence — that buffers the message
    // and any subsequent sendText alongside it, so the model only replies
    // after everything has piled up. With turnComplete each sendText
    // triggers an immediate response (and a second one interrupts the first).
    this._send({
      clientContent: {
        turns: [{ role: 'user', parts: [{ text }] }],
        turnComplete: true,
      },
    })
  }

  /**
   * Reply to a `tool-call` from the model. Pairs with the `tool-call` event;
   * the model pauses until this lands, then continues narrating with the
   * `response` payload available as the tool result.
   */
  sendToolResponse(id: string, name: string, response: unknown) {
    this._send({
      toolResponse: {
        functionResponses: [{ id, name, response }],
      },
    })
  }

  /**
   * Explicitly close the current user turn. Kept for completeness; do NOT
   * call this from a press-to-talk release path on this preview model —
   * it cancels the model's in-flight response and the tool-call step is
   * skipped. VAD silence detection is the reliable end-of-turn signal here.
   */
  sendTurnComplete() {
    this._send({ clientContent: { turnComplete: true } })
  }

  sendAudioChunk(pcm16: ArrayBuffer) {
    const data = bytesToBase64(new Uint8Array(pcm16))
    // Vertex Live API expects realtimeInput.audio (single Blob); the legacy
    // mediaChunks shape is silently ignored on this surface — text turns work
    // because realtimeInput.text is unambiguous.
    this._send({
      realtimeInput: {
        audio: { mimeType: 'audio/pcm;rate=16000', data },
      },
    })
  }

  isConnected(): boolean {
    return this.connected
  }

  close() {
    try {
      this.ws?.close()
    } catch {}
    this.ws = null
    this.connected = false
  }

  private _send(obj: unknown) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    this.ws.send(JSON.stringify(obj))
  }

  private _handleMessage(raw: unknown, onSetup: () => void) {
    const text =
      typeof raw === 'string'
        ? raw
        : new TextDecoder().decode(raw as ArrayBuffer)
    let msg: any
    try {
      msg = JSON.parse(text)
    } catch {
      return
    }

    if (msg.setupComplete) {
      this.connected = true
      this._dispatch({ type: 'connected' })
      onSetup()
      return
    }

    if (msg.serverContent) {
      const sc = msg.serverContent
      // Diagnostic: surface unexpected top-level keys so the search-mode
      // transcript wiring can be tuned if Gemini Live shifts field names.
      // Log only NON-content keys (skip the chatty modelTurn).
      const keys = Object.keys(sc).filter((k) => k !== 'modelTurn')
      if (keys.length > 0) {
        // eslint-disable-next-line no-console
        console.debug('[GeminiLiveSession] serverContent keys', keys, sc)
      }
      const parts = sc.modelTurn?.parts as Array<any> | undefined
      if (parts) {
        for (const part of parts) {
          const inline = part.inlineData
          if (!inline?.data || !inline?.mimeType) continue
          const bytes = base64ToBytes(inline.data)
          if ((inline.mimeType as string).startsWith('video/')) {
            this._dispatch({
              type: 'video-chunk',
              mimeType: inline.mimeType,
              data: bytes,
            })
          } else if ((inline.mimeType as string).startsWith('audio/')) {
            this._dispatch({
              type: 'audio-chunk',
              mimeType: inline.mimeType,
              data: bytes,
            })
          }
        }
      }
      const ot = sc.outputTranscription
      if (ot?.text) {
        this._dispatch({
          type: 'transcript',
          role: 'model',
          text: ot.text,
          isFinal: !!ot.finished,
        })
      }
      const it = sc.inputTranscription
      if (it?.text) {
        this._dispatch({
          type: 'transcript',
          role: 'user',
          text: it.text,
          isFinal: !!it.finished,
        })
      }
      // End-of-turn signal. Only `turnComplete` is reliable — it fires
      // after all audio has been delivered. `generationComplete` fires
      // earlier (when token generation finishes) while audio is still
      // streaming, so listening to it gives premature end-of-turn signals.
      if (sc.turnComplete) {
        this._dispatch({ type: 'turn-complete' })
      }
    }

    if (msg.toolCall?.functionCalls) {
      for (const fc of msg.toolCall.functionCalls as Array<{
        id?: string
        name?: string
        args?: Record<string, unknown>
      }>) {
        if (!fc.name) continue
        this._dispatch({
          type: 'tool-call',
          id: fc.id ?? '',
          name: fc.name,
          args: fc.args ?? {},
        })
      }
    }

    if (msg.goAway) {
      this._dispatch({
        type: 'error',
        error: new Error(`goAway: ${msg.goAway.reason ?? 'session ending'}`),
      })
    }
  }

  private _dispatch(msg: LiveMessage) {
    this.dispatchEvent(new CustomEvent(msg.type, { detail: msg }))
  }
}

// ---- base64 helpers (browser, no deps) -----------------------------------

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(
      null,
      Array.from(bytes.subarray(i, i + chunk)),
    )
  }
  return btoa(binary)
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}
