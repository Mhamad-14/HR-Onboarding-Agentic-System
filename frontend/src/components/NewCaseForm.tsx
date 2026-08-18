import { useState } from 'react'
import { api, ApiError } from '../api/client'
import {
  WORKER_META,
  WORKER_ORDER,
  type CaseFormValues,
  type WorkerName,
} from '../api/types'
import { Alert, Panel, Spinner } from './ui'

export const EMPTY_FORM: CaseFormValues = {
  case_id: '',
  employee_id: '',
  employee_name: '',
  role: '',
  department: '',
  manager_email: '',
  start_date: '',
  resume_text: '',
  request_text: 'Complete the employee\'s post-hire onboarding.',
  requested_actions: [...WORKER_ORDER],
  preferred_language: 'English',
  training_format: 'online',
}

export default function NewCaseForm({
  onSubmitted,
  disabled,
}: {
  onSubmitted: (threadId: string) => void
  disabled: boolean
}) {
  const [form, setForm] = useState<CaseFormValues>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update<K extends keyof CaseFormValues>(key: K, value: CaseFormValues[K]) {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  function toggleAction(worker: WorkerName) {
    setForm((previous) => {
      const has = previous.requested_actions.includes(worker)
      const requested_actions = has
        ? previous.requested_actions.filter((item) => item !== worker)
        : [...previous.requested_actions, worker]
      return { ...previous, requested_actions }
    })
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const response = await api.submitCase(form)
      onSubmitted(response.thread_id)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(formatApiError(err))
      } else {
        setError(err instanceof Error ? err.message : 'Unexpected error while submitting the case.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Panel title="New onboarding case">
      <form className="form-grid" onSubmit={handleSubmit}>
        <div className="field span-2">
          <label htmlFor="case_id">
            Case ID <span className="hint">(3–80 characters, e.g. CASE-ENG-004)</span>
          </label>
          <input
            id="case_id"
            type="text"
            required
            minLength={3}
            maxLength={80}
            value={form.case_id}
            onChange={(event) => update('case_id', event.target.value)}
            placeholder="CASE-ENG-004"
          />
        </div>

        <div className="field">
          <label htmlFor="employee_id">Employee ID</label>
          <input
            id="employee_id"
            type="text"
            required
            minLength={3}
            maxLength={40}
            value={form.employee_id}
            onChange={(event) => update('employee_id', event.target.value)}
            placeholder="EMP-5000"
          />
        </div>
        <div className="field">
          <label htmlFor="employee_name">Employee name</label>
          <input
            id="employee_name"
            type="text"
            required
            minLength={2}
            maxLength={120}
            value={form.employee_name}
            onChange={(event) => update('employee_name', event.target.value)}
            placeholder="Lina Alomar"
          />
        </div>

        <div className="field">
          <label htmlFor="role">Role</label>
          <input
            id="role"
            type="text"
            required
            minLength={2}
            maxLength={100}
            value={form.role}
            onChange={(event) => update('role', event.target.value)}
            placeholder="Software Engineer"
          />
        </div>
        <div className="field">
          <label htmlFor="department">Department</label>
          <input
            id="department"
            type="text"
            required
            minLength={2}
            maxLength={100}
            value={form.department}
            onChange={(event) => update('department', event.target.value)}
            placeholder="Engineering"
          />
        </div>

        <div className="field">
          <label htmlFor="manager_email">Manager email</label>
          <input
            id="manager_email"
            type="email"
            required
            value={form.manager_email}
            onChange={(event) => update('manager_email', event.target.value)}
            placeholder="manager@example.com"
          />
        </div>
        <div className="field">
          <label htmlFor="start_date">
            Start date <span className="hint">(leave empty to trigger the “missing information” step)</span>
          </label>
          <input
            id="start_date"
            type="date"
            value={form.start_date}
            onChange={(event) => update('start_date', event.target.value)}
          />
        </div>

        <div className="field span-2">
          <label htmlFor="resume_text">Resume summary (minimum 30 characters)</label>
          <textarea
            id="resume_text"
            required
            minLength={30}
            maxLength={20000}
            value={form.resume_text}
            onChange={(event) => update('resume_text', event.target.value)}
            placeholder="Summarize the employee's relevant experience, skills, and training…"
          />
        </div>

        <div className="field span-2">
          <label htmlFor="request_text">Request text</label>
          <input
            id="request_text"
            type="text"
            minLength={5}
            maxLength={2000}
            value={form.request_text}
            onChange={(event) => update('request_text', event.target.value)}
          />
        </div>

        <div className="field span-2">
          <label>Requested agents</label>
          <div className="checkbox-group">
            {WORKER_ORDER.map((worker) => {
              const checked = form.requested_actions.includes(worker)
              return (
                <label
                  key={worker}
                  className={`checkbox-chip${checked ? ' checkbox-chip--checked' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleAction(worker)}
                  />
                  {WORKER_META[worker].icon} {WORKER_META[worker].label}
                </label>
              )
            })}
          </div>
        </div>

        <div className="field">
          <label htmlFor="preferred_language">Preferred language</label>
          <select
            id="preferred_language"
            value={form.preferred_language}
            onChange={(event) =>
              update('preferred_language', event.target.value as CaseFormValues['preferred_language'])
            }
          >
            <option value="English">English</option>
            <option value="Arabic">Arabic</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="training_format">Training format</label>
          <select
            id="training_format"
            value={form.training_format}
            onChange={(event) =>
              update('training_format', event.target.value as CaseFormValues['training_format'])
            }
          >
            <option value="online">Online</option>
            <option value="in_person">In person</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </div>

        {error ? (
          <div className="span-2">
            <Alert tone="error" title="Could not submit the case">
              {error}
            </Alert>
          </div>
        ) : null}

        <div className="span-2">
          <button
            type="submit"
            className="btn btn--primary btn--block"
            disabled={submitting || disabled || form.requested_actions.length === 0}
          >
            {submitting ? (
              <>
                <Spinner /> Starting workflow…
              </>
            ) : (
              <>Submit onboarding case</>
            )}
          </button>
        </div>
      </form>
    </Panel>
  )
}

export function formatApiError(error: ApiError): string {
  const detail = error.detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    // FastAPI 422 validation errors: [{ loc: [...], msg, type }]
    return detail
      .map((item) => {
        if (typeof item !== 'object' || item === null) return String(item)
        const record = item as { loc?: unknown; msg?: unknown }
        const loc = Array.isArray(record.loc)
          ? record.loc.filter((part) => typeof part === 'string').join('.')
          : ''
        return loc ? `${loc}: ${String(record.msg ?? 'invalid')}` : String(record.msg ?? 'invalid')
      })
      .join('\n')
  }
  return error.message
}
