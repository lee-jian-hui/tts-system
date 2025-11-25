import type { TargetFormat } from '../types'

interface Props {
  status: string
  bytes: number
  chunks: number
  latencyMs: number | null
  droppedNetworkFrames: number
  droppedPlaybackFrames: number
  targetFormat: TargetFormat
  sampleRate: number
  limitLiveBuffer: boolean
  onLimitLiveBufferChange: (value: boolean) => void
  voicesLoading: boolean
  voicesError: string | null
  lastError: string | null
  isStreaming: boolean
  // Stress test metrics (optional)
  stressTotal: number
  stressCompleted: number
  stressFailed: number
  isStressRunning: boolean
  stressInFlight: number
  stressMaxInFlight: number
  backendActiveStreams: number | null
  backendSessionsCompleted: number | null
  backendSessionsFailed: number | null
  historyActiveStreams: number[]
  historyStressInFlight: number[]
  backendRateLimitUsage: number | null
  historyRateLimitUsage: number[]
  backendRateLimitWindowRemaining: number | null
  queueDepth: number | null
  queueMaxsize: number | null
  workersBusy: number | null
  workersTotal: number | null
  queueFullTotal: number | null
  historyQueueDepth: number[]
  stressFailureReasons: Record<string, number>
}

export function StatusPanel({
  status,
  bytes,
  chunks,
  latencyMs,
  droppedNetworkFrames,
  droppedPlaybackFrames,
  targetFormat,
  sampleRate,
  limitLiveBuffer,
  onLimitLiveBufferChange,
  voicesLoading,
  voicesError,
  lastError,
  isStreaming,
  stressTotal,
  stressCompleted,
  stressFailed,
  isStressRunning,
  stressInFlight,
  stressMaxInFlight,
  backendActiveStreams,
  backendSessionsCompleted,
  backendSessionsFailed,
  historyActiveStreams,
  historyStressInFlight,
  backendRateLimitUsage,
  historyRateLimitUsage,
  backendRateLimitWindowRemaining,
  queueDepth,
  queueMaxsize,
  workersBusy,
  workersTotal,
  queueFullTotal,
  historyQueueDepth,
  stressFailureReasons,
}: Props) {
  const renderSparkline = (data: number[]) => {
    if (!data.length) return null
    const width = 100
    const height = 30
    const maxPoints = 30
    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1
    const points = data
      .map((value, idx) => {
        const offset = Math.max(0, maxPoints - data.length)
        const slotIndex = offset + idx
        const x =
          data.length === 1
            ? width / 2
            : (slotIndex / (maxPoints - 1)) * width
        const norm = (value - min) / range
        const y = height - norm * height
        return `${x},${y}`
      })
      .join(' ')
    return (
      <svg
        className="sparkline"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
      >
        <polyline
          fill="none"
          stroke="#a5b4fc"
          strokeWidth="1.5"
          points={points}
        />
      </svg>
    )
  }

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
        Dropped frames (network/backend):{' '}
        <span>{droppedNetworkFrames}</span>
      </p>
      <p>
        Dropped frames (playback/frontend):{' '}
        <span>{droppedPlaybackFrames}</span>
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
      {Object.keys(stressFailureReasons).length > 0 && (
        <div className="stress-failures">
          <div className="stress-failures-title">
            Stress failures by cause (top)
          </div>
          {Object.entries(stressFailureReasons)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([reason, count]) => (
              <div key={reason} className="stress-failure-row">
                <span className="stress-failure-reason">{reason}</span>
                <span className="stress-failure-count">{count}</span>
              </div>
            ))}
        </div>
      )}
      {stressTotal > 0 && (
        <p>
          <strong>Stress test:</strong>{' '}
          {stressCompleted}/{stressTotal} completed, {stressFailed} failed{' '}
          {isStressRunning ? '(running)' : '(finished)'}
        </p>
      )}
      {stressInFlight > 0 && (
        <p>
          In-flight stress sessions:{' '}
          <span>
            {stressInFlight} (peak {stressMaxInFlight})
          </span>
        </p>
      )}
      {(backendActiveStreams != null ||
        backendSessionsCompleted != null ||
        backendSessionsFailed != null ||
        backendRateLimitUsage != null ||
        backendRateLimitWindowRemaining != null ||
        historyStressInFlight.length > 0 ||
        historyActiveStreams.length > 0 ||
        historyRateLimitUsage.length > 0 ||
        historyQueueDepth.length > 0) && (
        <div className="backend-metrics-container">
          <h3>Backend / load metrics</h3>
          {(backendActiveStreams != null ||
            backendSessionsCompleted != null ||
            backendSessionsFailed != null ||
            backendRateLimitUsage != null ||
            backendRateLimitWindowRemaining != null ||
            queueDepth != null ||
            workersBusy != null ||
            queueFullTotal != null) && (
            <p>
              {backendActiveStreams != null && (
                <>
                  active streams {backendActiveStreams}
                  {', '}
                </>
              )}
              {backendSessionsCompleted != null && (
                <>
                  sessions completed {backendSessionsCompleted}
                  {', '}
                </>
              )}
              {backendSessionsFailed != null && (
                <>
                  sessions failed {backendSessionsFailed}
                  {', '}
                </>
              )}
              {backendRateLimitUsage != null && (
                <>
                  rate limit usage{' '}
                  {(backendRateLimitUsage * 100).toFixed(0)}
                  %
                </>
              )}
              {backendRateLimitWindowRemaining != null && (
                <>
                  {', '}window resets in{' '}
                  {backendRateLimitWindowRemaining.toFixed(0)}s
                </>
              )}
              {queueDepth != null && queueMaxsize != null && (
                <>
                  {', '}queue {queueDepth}/{queueMaxsize}
                </>
              )}
              {workersBusy != null && workersTotal != null && (
                <>
                  {', '}workers {workersBusy}/{workersTotal} busy
                </>
              )}
              {queueFullTotal != null && queueFullTotal > 0 && (
                <>
                  {', '}queue-full events {queueFullTotal}
                </>
              )}
            </p>
          )}
          {(historyStressInFlight.length > 0 ||
            historyActiveStreams.length > 0 ||
            historyRateLimitUsage.length > 0 ||
            historyQueueDepth.length > 0) && (
            <div className="metrics-charts">
              {historyStressInFlight.length > 0 && (
                <div className="metrics-chart">
                  <div className="metrics-chart-label">Stress in-flight</div>
                  {renderSparkline(historyStressInFlight)}
                </div>
              )}
              {historyActiveStreams.length > 0 && (
                <div className="metrics-chart">
                  <div className="metrics-chart-label">
                    Backend active streams
                  </div>
                  {renderSparkline(historyActiveStreams)}
                </div>
              )}
              {historyRateLimitUsage.length > 0 && (
                <div className="metrics-chart">
                  <div className="metrics-chart-label">
                    Rate-limit usage (% of max bucket)
                  </div>
                  {renderSparkline(historyRateLimitUsage)}
                </div>
              )}
              {historyQueueDepth.length > 0 && (
                <div className="metrics-chart">
                  <div className="metrics-chart-label">Session queue depth</div>
                  {renderSparkline(historyQueueDepth)}
                </div>
              )}
            </div>
          )}
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
