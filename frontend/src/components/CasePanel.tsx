import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { AuditEvent } from '../api/types'
import { EmptyState, Panel } from './ui'

export default function CasePanel({
  threadId,
  onSelect,
}: {
  threadId: string | null
  onSelect: (threadId: string) => void
}) {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!threadId) {
      setEvents([])
      setError(null)
      return
    }
    let cancelled = false
    api
      .caseEvents(threadId)
      .then((items) => {
        if (!cancelled) setEvents(items)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load audit events.')
      })
    return () => {
      cancelled = true
    }
  }, [threadId])

  return (
    <Panel
      title="Cases"
      action={
        threadId ? (
          <span className="chip chip--blue mono">{threadId}</span>
        ) : undefined
      }
    >
      {threadId ? (
        <div className="event-list">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => onSelect(threadId)}
          >
            Refresh case status
          </button>
          {error ? <p className="muted" style={{ fontSize: 13 }}>{error}</p> : null}
          {events.length === 0 ? (
            <p className="muted" style={{ fontSize: 13 }}>
              No audit events recorded yet.
            </p>
          ) : (
            events.map((event) => (
              <div key={event.event_id} className="event-item">
                <span className="event-item__time">
                  {new Date(event.created_at).toLocaleString()}
                </span>
                <div>
                  <div className="event-item__type">{event.event_type}</div>
                  <div className="event-item__payload">
                    {JSON.stringify(event.payload)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <EmptyState icon="📋">No case selected yet.</EmptyState>
      )}
    </Panel>
  )
}
