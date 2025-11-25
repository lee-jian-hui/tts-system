// Central place for frontend configuration and tunable constants.

function envInt(name: string, fallback: number): number {
  const raw = (import.meta.env as any)[name]
  if (raw == null) return fallback
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return parsed
}

export const STRESS_MAX_SESSIONS = envInt('VITE_STRESS_MAX_SESSIONS', 100)
export const STRESS_MAX_CONCURRENCY = envInt('VITE_STRESS_MAX_CONCURRENCY', 20)

export const STRESS_DEFAULT_SESSIONS = Math.min(20, STRESS_MAX_SESSIONS)
export const STRESS_DEFAULT_CONCURRENCY = Math.min(5, STRESS_MAX_CONCURRENCY)

export const METRICS_POLL_INTERVAL_MS = envInt(
  'VITE_METRICS_POLL_INTERVAL_MS',
  2000,
)
