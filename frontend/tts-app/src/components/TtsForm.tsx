import type { FormEvent } from 'react'
import type { TargetFormat, VoiceInfo } from '../types'

interface Props {
  text: string
  provider: string
  voice: string
  targetFormat: TargetFormat
  voices: VoiceInfo[]
  onTextChange: (value: string) => void
  onProviderChange: (value: string) => void
  onVoiceChange: (value: string) => void
  onTargetFormatChange: (value: TargetFormat) => void
  onSubmit: (e: FormEvent) => void
}

export function TtsForm({
  text,
  provider,
  voice,
  targetFormat,
  voices,
  onTextChange,
  onProviderChange,
  onVoiceChange,
  onTargetFormatChange,
  onSubmit,
}: Props) {
  const providerOptions = Array.from(new Set(voices.map((v) => v.provider)))

  const providerVoices = voices.filter((v) => v.provider === provider)

  return (
    <form onSubmit={onSubmit} className="tts-form">
      <div className="form-field">
        <label htmlFor="text">Text</label>
        <textarea
          id="text"
          rows={3}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
        />
      </div>

      <div className="form-field">
        <label htmlFor="provider">Provider</label>
        <select
          id="provider"
          value={provider}
          onChange={(e) => onProviderChange(e.target.value)}
        >
          {providerOptions.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
          {voices.length === 0 && (
            <>
              <option value="mock_tone">mock_tone</option>
              <option value="coqui_tts">coqui_tts</option>
            </>
          )}
        </select>
      </div>

      <div className="form-field">
        <label htmlFor="voice">Voice</label>
        <input
          id="voice"
          list="voice-options"
          value={voice}
          onChange={(e) => onVoiceChange(e.target.value)}
        />
        <datalist id="voice-options">
          {providerVoices.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name} ({v.language})
            </option>
          ))}
        </datalist>
      </div>

      <div className="form-field">
        <label htmlFor="target-format">Target format</label>
        <select
          id="target-format"
          value={targetFormat}
          onChange={(e) => onTargetFormatChange(e.target.value as TargetFormat)}
        >
          <option value="pcm16">pcm16 (raw / live)</option>
          <option value="wav">wav (file)</option>
          <option value="mp3">mp3 (file)</option>
        </select>
      </div>

      <button type="submit">Start Session</button>
    </form>
  )
}
