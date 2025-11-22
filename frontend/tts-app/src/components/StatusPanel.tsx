interface Props {
  status: string
  bytes: number
  chunks: number
  voicesLoading: boolean
  voicesError: string | null
  lastError: string | null
  isStreaming: boolean
}

export function StatusPanel({
  status,
  bytes,
  chunks,
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
