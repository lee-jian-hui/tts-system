import { FormEvent, useState } from 'react'
import './App.css'

const BASE_URL = 'http://localhost:8080'

type TargetFormat = 'pcm16' | 'wav' | 'mp3'

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
      await streamAudio(ws_url, payload.target_format)
    } catch (err) {
      console.error('Error creating session or streaming:', err)
      const message =
        err instanceof Error ? `${err.name}: ${err.message}` : String(err)
      setLastError(message)
      setStatus('Error while creating session or streaming. See error details below.')
    }
  }

  const streamAudio = async (wsUrl: string, format: TargetFormat) => {
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
        chunksArr.push(chunkBytes)
        totalBytes += chunkBytes.length
        setBytes(totalBytes)
        setChunks((c) => c + 1)
      } else if (msg.type === 'eos') {
        setStatus('Stream complete. Building audio blob...')
        ws.close()
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
    }
  }

  return (
    <div className="app">
      <h1>TTS Gateway Demo</h1>

      <form onSubmit={handleSubmit} className="tts-form">
        <div className="form-field">
          <label htmlFor="text">Text</label>
          <textarea
            id="text"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        <div className="form-field">
          <label htmlFor="provider">Provider</label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="mock_tone">Mock Tone</option>
            <option value="coqui_tts">Coqui TTS</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="voice">Voice</label>
          <input
            id="voice"
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
          />
        </div>

        <div className="form-field">
          <label htmlFor="target-format">Target format</label>
          <select
            id="target-format"
            value={targetFormat}
            onChange={(e) => setTargetFormat(e.target.value as TargetFormat)}
          >
            <option value="pcm16">pcm16 (raw)</option>
            <option value="wav">wav</option>
            <option value="mp3">mp3</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="sample-rate">Sample rate (Hz)</label>
          <input
            id="sample-rate"
            type="number"
            value={sampleRate}
            onChange={(e) => setSampleRate(Number(e.target.value) || 0)}
          />
        </div>

        <button type="submit">Start Session</button>
      </form>

      <section className="status-panel">
        <p>
          <strong>Status:</strong> {status}
        </p>
        <p>
          Bytes received: <span>{bytes}</span>
        </p>
        <p>
          Chunks: <span>{chunks}</span>
        </p>
        {lastError && (
          <p>
            <strong>Last error:</strong> {lastError}
          </p>
        )}
      </section>

      <section className="player-section">
        <audio
          id="audio-player"
          controls
          src={audioUrl ?? undefined}
        />
      </section>
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
