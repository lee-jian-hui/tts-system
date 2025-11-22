import { type FormEvent, useState, useEffect, useRef } from 'react'
import './App.css'
import { TtsForm } from './components/TtsForm'
import { StatusPanel } from './components/StatusPanel'
import { PlayerSection } from './components/PlayerSection'
import type { TargetFormat, VoiceInfo } from './types'

const BASE_URL = 'http://localhost:8080'

interface SessionResponse {
  session_id: string
  ws_url: string
}

interface AudioMessage {
  type: 'audio'
  seq: number
  data: string
}

interface EosMessage {
  type: 'eos'
}

type WsMessage = AudioMessage | EosMessage

function App() {
  const [text, setText] = useState('Hello KeyReply – streaming test!')
  const [provider, setProvider] = useState('coqui_tts')
  const [voice, setVoice] = useState('coqui-en-1')
  const [targetFormat, setTargetFormat] = useState<TargetFormat>('pcm16')
  const [sampleRate, setSampleRate] = useState(16000)

  const [status, setStatus] = useState('Idle')
  const [bytes, setBytes] = useState(0)
  const [chunks, setChunks] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)
  const [voices, setVoices] = useState<VoiceInfo[]>([])
  const [voicesLoading, setVoicesLoading] = useState(false)
  const [voicesError, setVoicesError] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)

  // Web Audio state for live PCM16 streaming
  const audioCtxRef = useRef<AudioContext | null>(null)
  const playheadRef = useRef<number>(0)
  const audioStartedRef = useRef<boolean>(false)

  const enqueuePcmChunk = (pcmBytes: Uint8Array, streamSampleRate: number) => {
    const ctx = audioCtxRef.current
    if (!ctx) return

    const frameCount = Math.floor(pcmBytes.byteLength / 2)
    if (frameCount <= 0) return

    const audioBuffer = ctx.createBuffer(1, frameCount, streamSampleRate)
    const channelData = audioBuffer.getChannelData(0)
    const view = new DataView(
      pcmBytes.buffer,
      pcmBytes.byteOffset,
      pcmBytes.byteLength,
    )

    for (let i = 0; i < frameCount; i += 1) {
      const sample = view.getInt16(i * 2, true) / 32768
      channelData[i] = sample
    }

    const source = ctx.createBufferSource()
    source.buffer = audioBuffer
    source.connect(ctx.destination)

    // Schedule sequentially to keep continuity.
    const now = ctx.currentTime
    const startTime = playheadRef.current > now ? playheadRef.current : now
    source.start(startTime)
    playheadRef.current = startTime + audioBuffer.duration
  }

  // Load available voices from backend on mount
  useEffect(() => {
    const loadVoices = async () => {
      setVoicesLoading(true)
      setVoicesError(null)
      try {
        const resp = await fetch(`${BASE_URL}/v1/voices`)
        if (!resp.ok) {
          const body = await resp.text()
          throw new Error(`HTTP ${resp.status}: ${body}`)
        }
        const data = (await resp.json()) as { voices: VoiceInfo[] }
        setVoices(data.voices)

        // Initialize provider/voice if not already valid
        if (data.voices.length > 0) {
          const first = data.voices[0]
          if (!data.voices.some((v) => v.provider === provider)) {
            setProvider(first.provider)
          }
          if (!data.voices.some((v) => v.id === voice)) {
            setVoice(first.id)
            setSampleRate(first.sample_rate_hz)
          }
        }
      } catch (err) {
        console.error('Failed to load voices:', err)
        const msg =
          err instanceof Error ? `${err.name}: ${err.message}` : String(err)
        setVoicesError(msg)
      } finally {
        setVoicesLoading(false)
      }
    }

    loadVoices().catch((err) => {
      console.error('Unexpected error loading voices:', err)
    })
  }, [])

  // When provider changes, ensure selected voice belongs to that provider
  useEffect(() => {
    const providerVoices = voices.filter((v) => v.provider === provider)
    if (providerVoices.length === 0) {
      return
    }
    if (!providerVoices.some((v) => v.id === voice)) {
      const first = providerVoices[0]
      setVoice(first.id)
      setSampleRate(first.sample_rate_hz)
    }
  }, [provider, voices, voice])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    setStatus('Creating session...')
    setLastError(null)
    setBytes(0)
    setChunks(0)
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
      setAudioUrl(null)
    }

    const payload = {
      provider,
      voice,
      text,
      target_format: targetFormat,
      sample_rate_hz: sampleRate,
      language: 'en-US',
    }

    // Ensure AudioContext is ready for live PCM16 streaming.
    if (targetFormat === 'pcm16') {
      if (!audioCtxRef.current) {
        const AC =
          window.AudioContext ||
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (window as any).webkitAudioContext
        audioCtxRef.current = new AC()
      }
      await audioCtxRef.current!.resume()
      playheadRef.current = audioCtxRef.current!.currentTime
      audioStartedRef.current = false
    }

    try {
      const resp = await fetch(`${BASE_URL}/v1/tts/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const body = await resp.text()
        throw new Error(`HTTP ${resp.status}: ${body}`)
      }
      const { session_id, ws_url } = (await resp.json()) as SessionResponse
      setStatus(`Session ${session_id} created. Connecting WebSocket...`)
      await streamAudio(ws_url, payload.target_format, payload.sample_rate_hz)
    } catch (err) {
      console.error('Error creating session or streaming:', err)
      const message =
        err instanceof Error ? `${err.name}: ${err.message}` : String(err)
      setLastError(message)
      setStatus('Error while creating session or streaming. See error details below.')
    }
  }

  const streamAudio = async (
    wsUrl: string,
    format: TargetFormat,
    streamSampleRate: number,
  ) => {
    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl)
    } catch (err) {
      console.error('Failed to construct WebSocket:', err)
      const message =
        err instanceof Error ? `${err.name}: ${err.message}` : String(err)
      setLastError(message)
      setStatus('Failed to open WebSocket.')
      return
    }
    const chunksArr: Uint8Array[] = []
    let totalBytes = 0

    setStatus('Streaming audio...')
    setIsStreaming(true)

    ws.onopen = () => {
      console.debug('WebSocket opened:', wsUrl)
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      let msg: WsMessage
      try {
        msg = JSON.parse(event.data) as WsMessage
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err, event.data)
        setLastError('Failed to parse WebSocket message. See console for details.')
        return
      }
      if (msg.type === 'audio') {
        const chunkBytes = base64ToBytes(msg.data)
        // Live streaming path for PCM16 via Web Audio.
        if (format === 'pcm16') {
          try {
            enqueuePcmChunk(chunkBytes, streamSampleRate)
              if (!audioStartedRef.current) {
                setStatus('Playing (live)...')
                audioStartedRef.current = true
              }
          } catch (err) {
            console.error('Failed to enqueue PCM chunk:', err)
            setLastError(
              'Failed to enqueue PCM chunk for playback. See console for details.',
            )
          }
        } else {
          // File-oriented path for container formats (wav/mp3).
          chunksArr.push(chunkBytes)
        }
        totalBytes += chunkBytes.length
        setBytes(totalBytes)
        setChunks((c) => c + 1)
      } else if (msg.type === 'eos') {
        if (format === 'pcm16') {
          setStatus(
            audioStartedRef.current
              ? 'Stream complete (live playback).'
              : 'Stream complete (no audio played).',
          )
        } else {
          setStatus('Stream complete. Building audio blob...')
        }
        ws.close()
        setIsStreaming(false)
        if (format !== 'pcm16') {
          const mime =
            format === 'mp3'
              ? 'audio/mpeg'
              : format === 'wav'
              ? 'audio/wav'
              : 'audio/raw'
          const blob = new Blob(chunksArr, { type: mime })
          const url = URL.createObjectURL(blob)
          setAudioUrl(url)

          const audioEl = document.getElementById('audio-player') as
            | HTMLAudioElement
            | null
          if (audioEl) {
            audioEl
              .play()
              .then(() => setStatus('Playing.'))
              .catch(() => setStatus('Ready (click play).'))
          } else {
            setStatus('Ready (audio element not found).')
          }
        }
      } else {
        console.warn('Received unknown WebSocket message type:', msg)
        setLastError(`Unknown WebSocket message type: ${(msg as any).type}`)
      }
    }

    ws.onerror = (event) => {
      console.error('WebSocket error', event)
      setLastError('WebSocket error (see console for event details).')
      setStatus('WebSocket error.')
    }

    ws.onclose = (event: CloseEvent) => {
      console.warn('WebSocket closed:', event)
      setStatus((s) =>
        s.startsWith('Streaming')
          ? `WebSocket closed unexpectedly (code=${event.code}, reason="${event.reason || 'none'}").`
          : s,
      )
      if (!event.wasClean) {
        setLastError(
          `WebSocket closed uncleanly (code=${event.code}, reason="${event.reason || 'none'}").`,
        )
      }
      setIsStreaming(false)
    }
  }

  return (
    <div className="app">
      <h1>TTS Gateway Demo</h1>

      <TtsForm
        text={text}
        provider={provider}
        voice={voice}
        targetFormat={targetFormat}
        sampleRate={sampleRate}
        voices={voices}
        onTextChange={setText}
        onProviderChange={setProvider}
        onVoiceChange={setVoice}
        onTargetFormatChange={setTargetFormat}
        onSampleRateChange={setSampleRate}
        onSubmit={handleSubmit}
      />

      <StatusPanel
        status={status}
        bytes={bytes}
        chunks={chunks}
        voicesLoading={voicesLoading}
        voicesError={voicesError}
        lastError={lastError}
        isStreaming={isStreaming}
      />

      <PlayerSection targetFormat={targetFormat} audioUrl={audioUrl} />
    </div>
  )
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64)
  const len = binary.length
  const bytes = new Uint8Array(len)
  for (let i = 0; i < len; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes
}

export default App
