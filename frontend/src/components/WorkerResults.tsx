import { useState } from 'react'
import { api, ApiError } from '../api/client'
import { WORKER_META, WORKER_ORDER, type WorkerResult } from '../api/types'
import { Chip, EmptyState, Panel, Spinner } from './ui'

export default function WorkerResults({
  workerResults,
  threadId,
}: {
  workerResults: Partial<Record<string, WorkerResult>>
  threadId: string
}) {
  const [draft, setDraft] = useState<{ name: string; content: string } | null>(null)
  const [loadingDraft, setLoadingDraft] = useState<string | null>(null)
  const [draftError, setDraftError] = useState<string | null>(null)

  const available = WORKER_ORDER.filter((worker) => workerResults[worker])

  async function loadDraft(name: string) {
    setLoadingDraft(name)
    setDraftError(null)
    try {
      const content = await api.draftContent(name)
      setDraft({ name, content })
    } catch (err) {
      setDraftError(err instanceof ApiError ? err.message : 'Could not load the draft.')
    } finally {
      setLoadingDraft(null)
    }
  }

  return (
    <Panel
      title="Agent results"
      action={
        threadId ? (
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => {
              api.caseDrafts(threadId).then((names) => {
                if (names.length > 0) loadDraft(names[0])
              })
            }}
          >
            Open first draft
          </button>
        ) : undefined
      }
    >
      {available.length === 0 ? (
        <EmptyState icon="🤖">
          No agent results yet. Submit a case to run the Training, HR Documents, and IT
          Provisioning agents.
        </EmptyState>
      ) : (
        <div className="worker-grid">
          {available.map((worker) => (
            <WorkerCard key={worker} worker={worker} result={workerResults[worker]!} />
          ))}
        </div>
      )}

      {draftError ? (
        <div style={{ marginTop: 16 }}>
          <Chip tone="red">{draftError}</Chip>
        </div>
      ) : null}

      {draft ? (
        <div style={{ marginTop: 16 }}>
          <p className="section-label">Draft preview · {draft.name}</p>
          <pre className="draft-content">{draft.content}</pre>
        </div>
      ) : null}

      {loadingDraft ? (
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          <Spinner /> Loading draft…
        </p>
      ) : null}
    </Panel>
  )
}

function WorkerCard({
  worker,
  result,
}: {
  worker: keyof typeof WORKER_META
  result: WorkerResult
}) {
  const meta = WORKER_META[worker]
  const hasRisks = result.risk_flags.length > 0
  const hasArtifacts = result.artifacts.length > 0
  const hasRecommendations = result.recommendations.length > 0
  const hasCitations = result.citations.length > 0

  return (
    <article className="worker-card">
      <div className="worker-card__head">
        <span className="worker-card__icon" aria-hidden="true">
          {meta.icon}
        </span>
        <h3 className="worker-card__name">{meta.label}</h3>
        <span className="worker-card__status">
          <Chip tone={hasRisks ? 'amber' : 'green'}>{hasRisks ? 'Review needed' : 'Ready'}</Chip>
        </span>
      </div>
      <div className="worker-card__body">
        <p className="worker-card__summary">{result.summary}</p>

        {hasRisks ? (
          <div>
            <p className="worker-card__section">Risk flags</p>
            <div className="badge-list">
              {result.risk_flags.map((flag) => (
                <span key={flag} className="badge badge--risk">
                  ⚠ {flag}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {hasRecommendations ? (
          <div>
            <p className="worker-card__section">Recommendations</p>
            <ul className="list">
              {result.recommendations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {hasArtifacts ? (
          <div>
            <p className="worker-card__section">Artifacts</p>
            <div className="badge-list">
              {result.artifacts.map((artifact) => (
                <span key={artifact} className="badge badge--artifact">
                  {artifact}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {hasCitations ? (
          <div>
            <p className="worker-card__section">
              Citations ({result.citations.length})
            </p>
            <ul className="list">
              {result.citations.map((citation) => (
                <li key={citation.source}>
                  <strong>{citation.source}</strong>
                  <span className="muted"> — {citation.excerpt}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </article>
  )
}
