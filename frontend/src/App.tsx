import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './api/client'
import type { CaseStatusResponse } from './api/types'
import ApprovalStep from './components/ApprovalStep'
import CaseDetail from './components/CaseDetail'
import CasePanel from './components/CasePanel'
import ConnectionStatus from './components/ConnectionStatus'
import NewCaseForm from './components/NewCaseForm'
import WorkerResults from './components/WorkerResults'
import { Alert } from './components/ui'
import { phaseOf } from './components/WorkflowProgress'

export default function App() {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [response, setResponse] = useState<CaseStatusResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadStatus = useCallback(
    async (id: string, { silent = false } = {}) => {
      if (!silent) setLoading(true)
      setError(null)
      try {
        const status = await api.caseStatus(id)
        setResponse(status)
        setThreadId(id)
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Unexpected error while loading the case.',
        )
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [],
  )

  function handleSubmitted(newThreadId: string) {
    void loadStatus(newThreadId)
  }

  function handleResolved() {
    if (threadId) void loadStatus(threadId)
  }

  useEffect(() => {
    if (!threadId || loading) return
    const phase = phaseOf(response)
    if (phase !== 'human_approval' && phase !== 'missing_information') return
    const timer = window.setInterval(() => {
      void loadStatus(threadId, { silent: true })
    }, 15_000)
    return () => window.clearInterval(timer)
  }, [threadId, response, loading, loadStatus])

  const phase = phaseOf(response)
  const showApproval = Boolean(threadId) && phase === 'human_approval'
  const showMissing = Boolean(threadId) && phase === 'missing_information'
  const workerResults = response?.outcome?.worker_results ??
                        response?.interrupt?.value?.worker_results ??
                        null

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <div className="brand">
            <span className="brand__logo" aria-hidden="true">
              🧑‍💼
            </span>
            <div>
              <h1 className="brand__title">OnboardAI</h1>
              <p className="brand__subtitle">Human-supervised HR onboarding dashboard</p>
            </div>
          </div>
          <ConnectionStatus />
        </div>
      </header>

      <main className="app-main">
        {error ? (
          <div style={{ marginBottom: 16 }}>
            <Alert tone="error" title="API error">
              {error}
            </Alert>
          </div>
        ) : null}

        <div className="grid grid--dashboard">
          <div className="stack">
            <NewCaseForm
              onSubmitted={handleSubmitted}
              disabled={loading || showApproval || showMissing}
            />
            <CasePanel threadId={threadId} onSelect={(id) => void loadStatus(id)} />
          </div>

          <div className="stack">
            <CaseDetail threadId={threadId} response={response} />
            {workerResults ? (
              <WorkerResults workerResults={workerResults} threadId={threadId ?? ''} />
            ) : (
              <WorkerResults workerResults={{}} threadId={threadId ?? ''} />
            )}

            {showApproval && threadId ? (
              <ApprovalStep
                threadId={threadId}
                approvedActions={response?.interrupt?.value.proposed_actions ?? []}
                onResolved={handleResolved}
              />
            ) : null}

            {showMissing && threadId ? (
              <MissingInformationStep
                threadId={threadId}
                onResolved={handleResolved}
              />
            ) : null}

            
          </div>
        </div>
      </main>

      <footer className="app-footer">
        OnboardAI · Track A Supervisor + Workers · Orchestrator-Worker pattern · Hybrid RAG
      </footer>
    </div>
  )
}

function MissingInformationStep({
  threadId,
  onResolved,
}: {
  threadId: string
  onResolved: () => void
}) {
  const [startDate, setStartDate] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.resumeCase(threadId, { start_date: startDate })
      onResolved()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Unexpected error while resuming the case.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel__header">
        <h2 className="panel__title">Missing information</h2>
      </div>
      <div className="panel__body">
        <form className="flow" onSubmit={handleSubmit}>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            The workflow paused because the start date is required before the supervisor can plan
            the onboarding. Provide it below and resume the same thread.
          </p>
          <div className="field">
            <label htmlFor="missing_start_date">Start date</label>
            <input
              id="missing_start_date"
              type="date"
              required
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </div>
          {error ? <Alert tone="error" title="Could not resume">{error}</Alert> : null}
          <button type="submit" className="btn btn--primary" disabled={submitting || !startDate}>
            {submitting ? 'Resuming…' : 'Provide start date and continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
