import type { FormEvent } from 'react'

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
      <h2>Stress Test (experimental)</h2>
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
          max={100}
          value={sessions}
          onChange={(e) => onSessionsChange(Number(e.target.value) || 0)}
          disabled={isBusy}
        />
      </div>
      <div className="form-field-inline">
        <label htmlFor="stress-concurrency">Max concurrency</label>
        <input
          id="stress-concurrency"
          type="number"
          min={1}
          max={20}
          value={concurrency}
          onChange={(e) => onConcurrencyChange(Number(e.target.value) || 0)}
          disabled={isBusy}
        />
      </div>
      <button type="submit" disabled={isBusy}>
        Start Stress Test
      </button>
    </form>
  )
}

