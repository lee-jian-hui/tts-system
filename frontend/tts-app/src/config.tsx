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

// Default values for the stress form. These can be set explicitly via env,
// and fall back to the configured max values so that a single click can run
// a maximum-intensity stress test if desired.
export const STRESS_DEFAULT_SESSIONS = envInt(
  'VITE_STRESS_DEFAULT_SESSIONS',
  STRESS_MAX_SESSIONS,
)
export const STRESS_DEFAULT_CONCURRENCY = envInt(
  'VITE_STRESS_DEFAULT_CONCURRENCY',
  STRESS_MAX_CONCURRENCY,
)

export const METRICS_POLL_INTERVAL_MS = envInt(
  'VITE_METRICS_POLL_INTERVAL_MS',
  2000,
)
