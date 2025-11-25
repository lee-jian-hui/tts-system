import type { FormEvent } from 'react'
import {
  STRESS_MAX_CONCURRENCY,
  STRESS_MAX_SESSIONS,
} from '../config'

interface Props {
  isBusy: boolean
  sessions: number
  concurrency: number
  onSessionsChange: (value: number) => void
  onConcurrencyChange: (value: number) => void
  onSubmit: (e: FormEvent) => void
}

export function StressForm({
  isBusy,
  sessions,
  concurrency,
  onSessionsChange,
  onConcurrencyChange,
  onSubmit,
}: Props) {
  return (
    <form onSubmit={onSubmit} className="stress-form">
      <h2>Stress Test</h2>
      <p className="stress-help">
        Fire multiple synthetic TTS sessions against the backend. Audio is not
        played, only metrics are collected. Use conservative values on your
        local machine.
      </p>
      <div className="form-field-inline">
        <label htmlFor="stress-sessions">Total sessions</label>
        <input
          id="stress-sessions"
          type="number"
          min={1}
          max={STRESS_MAX_SESSIONS}
          value={sessions === 0 ? '' : sessions}
          onChange={(e) => {
            const raw = e.target.value
            const next = raw === '' ? 0 : Number(raw)
            onSessionsChange(Number.isNaN(next) ? 0 : next)
          }}
          disabled={isBusy}
        />
      </div>
      <div className="form-field-inline">
        <label htmlFor="stress-concurrency">Max concurrency</label>
        <input
          id="stress-concurrency"
          type="number"
          min={1}
          max={STRESS_MAX_CONCURRENCY}
          value={concurrency === 0 ? '' : concurrency}
          onChange={(e) => {
            const raw = e.target.value
            const next = raw === '' ? 0 : Number(raw)
            onConcurrencyChange(Number.isNaN(next) ? 0 : next)
          }}
          disabled={isBusy}
        />
      </div>
      <button type="submit" disabled={isBusy}>
        Start Stress Test
      </button>
    </form>
  )
}
