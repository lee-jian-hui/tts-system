import type { TargetFormat } from '../types'

interface Props {
  targetFormat: TargetFormat
  audioUrl: string | null
}

export function PlayerSection({ targetFormat, audioUrl }: Props) {
  return (
    <section className="player-section">
      {targetFormat !== 'pcm16' && (
        <>
          <audio
            id="audio-player"
            controls
            src={audioUrl ?? undefined}
          />
          {audioUrl && (
            <a
              href={audioUrl}
              download={
                targetFormat === 'mp3'
                  ? 'tts-output.mp3'
                  : 'tts-output.wav'
              }
              className="download-link"
            >
              Download audio
            </a>
          )}
        </>
      )}
      {targetFormat === 'pcm16' && (
        <p className="live-hint">
          Live PCM16 stream is played via Web Audio (no file).
        </p>
      )}
    </section>
  )
}
