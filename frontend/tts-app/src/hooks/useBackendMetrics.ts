import { useEffect, useState } from 'react'

interface BackendMetricsState {
  activeStreams: number | null
  sessionsCompleted: number | null
  sessionsFailed: number | null
  rateLimitUsage: number | null
  rateLimitWindowRemaining: number | null
  historyActiveStreams: number[]
  historyRateLimitUsage: number[]
  historyStressInFlight: number[]
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
    historyActiveStreams: [],
    historyRateLimitUsage: [],
    historyStressInFlight: [],
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

          return {
            activeStreams,
            sessionsCompleted,
            sessionsFailed,
            rateLimitUsage,
            rateLimitWindowRemaining,
            historyActiveStreams: trimmedActive,
            historyStressInFlight: trimmedStress,
            historyRateLimitUsage: trimmedRate,
          }
        })
      } catch {
        // Ignore metrics errors in the UI.
      }
    }

    void pollMetrics()
    const id = window.setInterval(() => {
      void pollMetrics()
    }, 2000)

    return () => {
      window.clearInterval(id)
    }
  }, [baseUrl, isStressRunning, stressInFlight])

  return state
}
