import { useState, useRef, useCallback } from 'react'

interface AudioRecorderState {
  isRecording: boolean
  audioBlob: Blob | null
  audioBase64: string | null
  error: string | null
  secondsLeft: number | null
}

export function useAudioRecorder(maxDurationMs = 10_000) {
  const [state, setState] = useState<AudioRecorderState>({
    isRecording: false,
    audioBlob: null,
    audioBase64: null,
    error: null,
    secondsLeft: null,
  })

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startTimeRef = useRef<number>(0)

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current)
      autoStopRef.current = null
    }
    if (mediaRecorderRef.current?.stream) {
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop())
    }
    mediaRecorderRef.current = null
  }, [])

  const blobToBase64 = (blob: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => {
        const dataUrl = reader.result as string
        // Strip "data:audio/webm;codecs=opus;base64," prefix
        const base64 = dataUrl.split(',')[1]
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(blob)
    })
  }

  const startRecording = useCallback(async () => {
    // Reset previous state
    chunksRef.current = []
    setState({
      isRecording: true,
      audioBlob: null,
      audioBase64: null,
      error: null,
      secondsLeft: Math.ceil(maxDurationMs / 1000),
    })

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      recorder.onstop = async () => {
        cleanup()
        const blob = new Blob(chunksRef.current, { type: mimeType })
        const base64 = await blobToBase64(blob)
        setState((prev) => ({
          ...prev,
          isRecording: false,
          audioBlob: blob,
          audioBase64: base64,
          secondsLeft: null,
        }))
      }

      recorder.start()
      startTimeRef.current = Date.now()

      // Countdown timer
      timerRef.current = setInterval(() => {
        const elapsed = Date.now() - startTimeRef.current
        const remaining = Math.max(
          0,
          Math.ceil((maxDurationMs - elapsed) / 1000)
        )
        setState((prev) => ({ ...prev, secondsLeft: remaining }))
      }, 500)

      // Auto-stop after max duration
      autoStopRef.current = setTimeout(() => {
        if (
          mediaRecorderRef.current &&
          mediaRecorderRef.current.state === 'recording'
        ) {
          mediaRecorderRef.current.stop()
        }
      }, maxDurationMs)
    } catch (err) {
      cleanup()
      const message =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Microphone permission denied'
          : 'Failed to start recording'
      setState({
        isRecording: false,
        audioBlob: null,
        audioBase64: null,
        error: message,
        secondsLeft: null,
      })
    }
  }, [maxDurationMs, cleanup])

  const stopRecording = useCallback(() => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === 'recording'
    ) {
      mediaRecorderRef.current.stop()
    }
  }, [])

  const reset = useCallback(() => {
    cleanup()
    setState({
      isRecording: false,
      audioBlob: null,
      audioBase64: null,
      error: null,
      secondsLeft: null,
    })
  }, [cleanup])

  return {
    isRecording: state.isRecording,
    audioBlob: state.audioBlob,
    audioBase64: state.audioBase64,
    error: state.error,
    secondsLeft: state.secondsLeft,
    startRecording,
    stopRecording,
    reset,
  }
}
