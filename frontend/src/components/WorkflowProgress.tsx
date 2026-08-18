import type { CaseStatusResponse, InterruptPayload, WorkerName } from '../api/types'
import { Chip } from './ui'

export type WorkflowPhase = 'missing_information' | 'human_approval' | 'completed' | 'rejected'

export function phaseOf(response: CaseStatusResponse | null): WorkflowPhase {
  if (!response) return 'human_approval'
  if (response.outcome) {
    return response.outcome.status === 'completed' ? 'completed' : 'rejected'
  }
  if (response.interrupt) {
    return response.interrupt.type
  }
  return 'human_approval'
}

export function phaseLabel(phase: WorkflowPhase): string {
  switch (phase) {
    case 'missing_information':
      return 'Missing information'
    case 'human_approval':
      return 'Awaiting approval'
    case 'completed':
      return 'Completed'
    case 'rejected':
      return 'Rejected'
  }
}

export function phaseTone(phase: WorkflowPhase): 'amber' | 'blue' | 'green' | 'red' {
  switch (phase) {
    case 'missing_information':
      return 'amber'
    case 'human_approval':
      return 'blue'
    case 'completed':
      return 'green'
    case 'rejected':
      return 'red'
  }
}

export function interruptStep(
  interrupt: InterruptPayload | null,
): { worker: WorkerName; label: string } {
  if (interrupt?.type === 'missing_information') {
    return { worker: 'hr_documents', label: 'Request information' }
  }
  return { worker: 'training', label: 'Human approval' }
}

export default function WorkflowProgress({ response }: { response: CaseStatusResponse | null }) {
  const phase = phaseOf(response)
  const stageIndex = stageIndexOf(phase)

  const stages = [
    { label: 'Submit' },
    { label: 'Validate' },
    { label: 'Supervisor plan' },
    { label: 'Agents' },
    { label: 'Synthesis & drafts' },
    { label: 'Human approval' },
    { label: 'Finalize' },
  ]

  return (
    <div className="workflow-steps" aria-label={`Workflow status: ${phaseLabel(phase)}`}>
      {stages.map((stage, index) => {
        const state =
          phase === 'rejected' && index === stages.length - 1
            ? 'rejected'
            : index < stageIndex
              ? 'done'
              : index === stageIndex
                ? 'active'
                : 'pending'
        return (
          <div
            key={stage.label}
            className={`workflow-step workflow-step--${state}`}
            title={stage.label}
          >
            {index > 0 ? (
              <span
                className={`workflow-step__bar${state === 'done' ? ' workflow-step__bar--filled' : ''}`}
              />
            ) : null}
            <span className="workflow-step__dot">{state === 'done' ? '✓' : index + 1}</span>
            <span className="workflow-step__label">{stage.label}</span>
          </div>
        )
      })}
      <div style={{ marginLeft: 12 }}>
        <Chip tone={phaseTone(phase)}>{phaseLabel(phase)}</Chip>
      </div>
    </div>
  )
}

function stageIndexOf(phase: WorkflowPhase): number {
  switch (phase) {
    case 'missing_information':
      return 1
    case 'human_approval':
      return 5
    case 'completed':
      return 6
    case 'rejected':
      return 6
  }
}
