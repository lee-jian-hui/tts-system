import type { TargetFormat } from '../types'

interface Props {
  status: string
  bytes: number
  chunks: number
  latencyMs: number | null
  droppedFrames: number
  targetFormat: TargetFormat
  sampleRate: number
  limitLiveBuffer: boolean
  onLimitLiveBufferChange: (value: boolean) => void
  voicesLoading: boolean
  voicesError: string | null
  lastError: string | null
  isStreaming: boolean
}

export function StatusPanel({
  status,
  bytes,
  chunks,
  latencyMs,
  droppedFrames,
  targetFormat,
  sampleRate,
  limitLiveBuffer,
  onLimitLiveBufferChange,
  voicesLoading,
  voicesError,
  lastError,
  isStreaming,
}: Props) {
  return (
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
      <p>
        Format:{' '}
        <span>
          {targetFormat} @ {sampleRate} Hz
        </span>
      </p>
      {latencyMs != null && (
        <p>
          First chunk latency:{' '}
          <span>{latencyMs.toFixed(0)} ms</span>
        </p>
      )}
      <p>
        Dropped frames: <span>{droppedFrames}</span>
      </p>
      {targetFormat === 'pcm16' && (
        <p>
          <label>
            <input
              type="checkbox"
              checked={limitLiveBuffer}
              onChange={(e) => onLimitLiveBufferChange(e.target.checked)}
            />{' '}
            Limit live buffer to ~2s (drop extra chunks)
          </label>
        </p>
      )}
      {isStreaming && (
        <div className="streaming-indicator">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      )}
      {voicesLoading && <p>Loading voices...</p>}
      {voicesError && (
        <p>
          <strong>Voice load error:</strong> {voicesError}
        </p>
      )}
      {lastError && (
        <p>
          <strong>Last error:</strong> {lastError}
        </p>
      )}
    </section>
  )
}
