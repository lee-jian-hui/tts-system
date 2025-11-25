import { useEffect, useState } from 'react'
import { METRICS_POLL_INTERVAL_MS } from '../config'

interface BackendMetricsState {
  activeStreams: number | null
  sessionsCompleted: number | null
  sessionsFailed: number | null
  rateLimitUsage: number | null
  rateLimitWindowRemaining: number | null
  queueDepth: number | null
  queueMaxsize: number | null
  workersBusy: number | null
  workersTotal: number | null
  queueFullTotal: number | null
  historyActiveStreams: number[]
  historyRateLimitUsage: number[]
  historyStressInFlight: number[]
  historyQueueDepth: number[]
}

/**
 * Polls the backend Prometheus `/metrics` endpoint and exposes a small set
 * of aggregated metrics plus short history buffers for simple charting.
 */
export function useBackendMetrics(
  baseUrl: string,
  isStressRunning: boolean,
  stressInFlight: number,
): BackendMetricsState {
  const [state, setState] = useState<BackendMetricsState>({
    activeStreams: null,
    sessionsCompleted: null,
    sessionsFailed: null,
    rateLimitUsage: null,
    rateLimitWindowRemaining: null,
    queueDepth: null,
    queueMaxsize: null,
    workersBusy: null,
    workersTotal: null,
    queueFullTotal: null,
    historyActiveStreams: [],
    historyRateLimitUsage: [],
    historyStressInFlight: [],
    historyQueueDepth: [],
  })

  useEffect(() => {
    const pollMetrics = async () => {
      try {
        const resp = await fetch(`${baseUrl}/metrics`)
        if (!resp.ok) {
          return
        }
        const text = await resp.text()

        let activeStreams = 0
        let sessionsCompleted = 0
        let sessionsFailed = 0
        let rateLimitUsage: number | null = null
        let rateLimitWindowRemaining: number | null = null
        let queueDepth: number | null = null
        let queueMaxsize: number | null = null
        let workersBusy: number | null = null
        let workersTotal: number | null = null
        let queueFullTotal: number | null = null

        const lines = text.split('\n')
        for (const line of lines) {
          if (line.startsWith('tts_active_streams')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              activeStreams += value
            }
          } else if (line.startsWith('tts_sessions_total')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (Number.isNaN(value)) continue
            if (line.includes('status="completed"')) {
              sessionsCompleted += value
            } else if (line.includes('status="failed"')) {
              sessionsFailed += value
            }
          } else if (line.startsWith('tts_rate_limit_max_bucket_usage')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              rateLimitUsage = value
            }
          } else if (
            line.startsWith('tts_rate_limit_window_remaining_seconds')
          ) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              rateLimitWindowRemaining = value
            }
          } else if (line.startsWith('tts_session_queue_depth')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              queueDepth = value
            }
          } else if (line.startsWith('tts_session_queue_maxsize')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              queueMaxsize = value
            }
          } else if (line.startsWith('tts_session_workers_busy')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              workersBusy = value
            }
          } else if (line.startsWith('tts_session_workers_total')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              workersTotal = value
            }
          } else if (line.startsWith('tts_session_queue_full_total')) {
            const parts = line.trim().split(/\s+/)
            const value = Number.parseFloat(parts[parts.length - 1])
            if (!Number.isNaN(value)) {
              queueFullTotal = value
            }
          }
        }

        setState((prev) => {
          const nextHistoryActive = [
            ...prev.historyActiveStreams,
            activeStreams,
          ]
          const trimmedActive =
            nextHistoryActive.length > 30
              ? nextHistoryActive.slice(nextHistoryActive.length - 30)
              : nextHistoryActive

          const nextHistoryStress = isStressRunning
            ? [...prev.historyStressInFlight, stressInFlight]
            : prev.historyStressInFlight
          const trimmedStress =
            nextHistoryStress.length > 30
              ? nextHistoryStress.slice(nextHistoryStress.length - 30)
              : nextHistoryStress

          const nextHistoryRate =
            rateLimitUsage != null
              ? [...prev.historyRateLimitUsage, rateLimitUsage]
              : prev.historyRateLimitUsage
          const trimmedRate =
            nextHistoryRate.length > 30
              ? nextHistoryRate.slice(nextHistoryRate.length - 30)
              : nextHistoryRate

          const nextHistoryQueue =
            queueDepth != null
              ? [...prev.historyQueueDepth, queueDepth]
              : prev.historyQueueDepth
          const trimmedQueue =
            nextHistoryQueue.length > 30
              ? nextHistoryQueue.slice(nextHistoryQueue.length - 30)
              : nextHistoryQueue

          return {
            activeStreams,
            sessionsCompleted,
            sessionsFailed,
            rateLimitUsage,
            rateLimitWindowRemaining,
            historyActiveStreams: trimmedActive,
            historyStressInFlight: trimmedStress,
            historyRateLimitUsage: trimmedRate,
            queueDepth,
            queueMaxsize,
            workersBusy,
            workersTotal,
            queueFullTotal,
            historyQueueDepth: trimmedQueue,
          }
        })
      } catch {
        // Ignore metrics errors in the UI.
      }
    }

    void pollMetrics()
    const id = window.setInterval(() => {
      void pollMetrics()
    }, METRICS_POLL_INTERVAL_MS)

    return () => {
      window.clearInterval(id)
    }
  }, [baseUrl, isStressRunning, stressInFlight])

  return state
}
