export type TargetFormat = 'pcm16' | 'wav' | 'mp3'

export interface VoiceInfo {
  id: string
  name: string
  language: string
  provider: string
  sample_rate_hz: number
  supported_formats: string[]
}

