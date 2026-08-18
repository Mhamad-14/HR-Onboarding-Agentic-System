import { useState } from 'react'
import { api, ApiError } from '../api/client'
import type { WorkerName } from '../api/types'
import { Alert, Panel, Spinner } from './ui'

export default function ApprovalStep({
  threadId,
  approvedActions,
  onResolved,
}: {
  threadId: string
  approvedActions: WorkerName[]
  onResolved: () => void
}) {
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null)
  const [reviewer, setReviewer] = useState('')
  const [comments, setComments] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!decision) return
    setSubmitting(true)
    setError(null)
    try {
      await api.resumeCase(threadId, {
        approved: decision === 'approve',
        reviewer: reviewer.trim() || 'HR Dashboard Reviewer',
        comments: comments.trim(),
        approved_actions: decision === 'approve' ? approvedActions : [],
      })
      onResolved()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : 'Unexpected error while resuming the case.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Panel title="Human approval required">
      <div className="approval-box">
        <p className="approval-box__title">
          <span aria-hidden="true">🧑‍💼</span> Review drafts and proposed actions before approval
        </p>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Resuming with <strong>approve</strong> finalizes the sandboxed IT ticket, marks HR
          document drafts as reviewed, and records approved training. Resuming with{' '}
          <strong>reject</strong> stops the workflow without consequential actions.
        </p>

        <form className="flow" onSubmit={handleSubmit}>
          <div className="approval-toggle" role="group" aria-label="Approval decision">
            <button
              type="button"
              className={`btn${decision === 'approve' ? ' btn--selected-approve' : ' btn--ghost'}`}
              onClick={() => setDecision('approve')}
            >
              ✅ Approve
            </button>
            <button
              type="button"
              className={`btn${decision === 'reject' ? ' btn--selected-reject' : ' btn--danger'}`}
              onClick={() => setDecision('reject')}
            >
              ⛔ Reject
            </button>
          </div>

          <div className="field">
            <label htmlFor="reviewer">Reviewer name</label>
            <input
              id="reviewer"
              type="text"
              minLength={2}
              maxLength={120}
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              placeholder="HR Dashboard Reviewer"
            />
          </div>

          <div className="field">
            <label htmlFor="comments">Comments</label>
            <textarea
              id="comments"
              maxLength={1000}
              value={comments}
              onChange={(event) => setComments(event.target.value)}
              placeholder="Optional review comments…"
            />
          </div>

          {error ? <Alert tone="error" title="Could not resume the case">{error}</Alert> : null}

          <button
            type="submit"
            className="btn btn--primary"
            disabled={!decision || submitting}
          >
            {submitting ? (
              <>
                <Spinner /> Resuming workflow…
              </>
            ) : (
              <>Submit decision</>
            )}
          </button>
        </form>
      </div>
    </Panel>
  )
}
