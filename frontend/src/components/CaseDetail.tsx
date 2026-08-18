import type { CaseStatusResponse } from '../api/types'
import { Chip, EmptyState, Panel } from './ui'
import WorkflowProgress, { interruptStep, phaseLabel, phaseOf } from './WorkflowProgress'

export default function CaseDetail({
  threadId,
  response,
}: {
  threadId: string | null
  response: CaseStatusResponse | null
}) {
  if (!threadId) {
    return (
      <Panel title="Case status">
        <EmptyState icon="🧭">
          Submit a new onboarding case to see its status, workflow progress, and agent results.
        </EmptyState>
      </Panel>
    )
  }

  if (!response) {
    return (
      <Panel title="Case status">
        <EmptyState icon="⏳">Loading the case from the backend…</EmptyState>
      </Panel>
    )
  }

  const interrupt = response.interrupt
  const outcome = response.outcome
  const phase = phaseOf(response)
  const interruptInfo = interrupt ? interruptStep(interrupt) : null

  const caseId =
    outcome?.case_id ??
    interrupt?.value.case_id ??
    (threadId.split('-').slice(0, 3).join('-') || threadId)

  const employeeId = outcome?.employee_id ?? interrupt?.value.employee_id ?? '—'
  const riskFlags = interrupt?.value.risk_flags ?? outcome?.synthesis.key_risks ?? []
  const proposedActions = interrupt?.value.proposed_actions ?? []
  const draftPaths = interrupt?.value.draft_paths ?? []

  return (
    <div className="stack">
      <Panel
        title={
          <>
            <span className="chip chip--blue mono">{caseId}</span>{' '}
            <span className="muted" style={{ fontWeight: 500, fontSize: 14 }}>
              thread {threadId}
            </span>
          </>
        }
        action={<Chip tone="gray">Phase: {phaseLabel(phase)}</Chip>}
      >
        <WorkflowProgress response={response} />

        <dl className="kv">
          <dt>Employee</dt>
          <dd>{employeeId}</dd>
          <dt>Requested agents</dt>
          <dd>
            {proposedActions.length > 0
              ? proposedActions.join(', ')
              : outcome?.synthesis.completed_workers.join(', ') ?? '—'}
          </dd>
          <dt>Message</dt>
          <dd>{interrupt?.value.message ?? outcome?.synthesis.summary ?? '—'}</dd>
        </dl>

        {interrupt ? (
          <>
            <div className="divider" />
            <p className="section-label">
              {interrupt.type === 'human_approval'
                ? 'Pending human approval'
                : 'Pending information'}
            </p>
            <Chip tone={interrupt.type === 'human_approval' ? 'blue' : 'amber'}>
              {interrupt.type === 'human_approval'
                ? '🧑‍💼 Awaiting HR review'
                : `Missing field: ${String(interrupt.value.field ?? 'unknown')}`}
            </Chip>
            {interruptInfo ? (
              <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
                Next resume handoff: <strong>{interruptInfo.label}</strong>
              </p>
            ) : null}
          </>
        ) : null}

        {riskFlags.length > 0 ? (
          <>
            <div className="divider" />
            <p className="section-label">Risk flags</p>
            <div className="badge-list">
              {riskFlags.map((flag) => (
                <span key={flag} className="badge badge--risk">
                  ⚠ {flag}
                </span>
              ))}
            </div>
          </>
        ) : null}

        {draftPaths.length > 0 ? (
          <>
            <div className="divider" />
            <p className="section-label">Generated draft files</p>
            <div className="draft-list">
              {draftPaths.map((path) => (
                <div key={path} className="draft-item">
                  <span className="draft-item__name">{path}</span>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </Panel>

      {outcome ? (
        <Panel title="Final outcome">
          <dl className="kv">
            <dt>Status</dt>
            <dd>
              <Chip tone={outcome.status === 'completed' ? 'green' : 'red'}>
                {outcome.status === 'completed' ? 'Completed' : 'Rejected'}
              </Chip>
            </dd>
            {outcome.approval ? (
              <>
                <dt>Reviewer</dt>
                <dd>{outcome.approval.reviewer}</dd>
                <dt>Comments</dt>
                <dd>{outcome.approval.comments || '—'}</dd>
              </>
            ) : null}
            <dt>Final actions</dt>
            <dd>
              {outcome.final_actions.length > 0 ? (
                <ul className="list">
                  {outcome.final_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              ) : (
                'None'
              )}
            </dd>
          </dl>
        </Panel>
      ) : null}
    </div>
  )
}
