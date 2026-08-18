import type {
  AuditEvent,
  CaseFormValues,
  CaseStatusResponse,
  CaseSubmitResponse,
  HealthResponse,
  OnboardingOutcome,
  SupervisorDecision,
} from './types'

/**
 * Thin client for the OnboardAI FastAPI backend.
 *
 * In development the Vite server proxies /api to http://127.0.0.1:8002.
 * For a production build, set VITE_API_BASE_URL to the backend origin
 * (for example http://127.0.0.1:8002) and the backend must allow the
 * dashboard origin via CORS.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    let detail: unknown
    try {
      detail = await response.json()
    } catch {
      detail = await response.text().catch(() => null)
    }
    const message =
      typeof detail === 'object' && detail !== null && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`
    throw new ApiError(response.status, detail, message)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  health(): Promise<HealthResponse> {
    return request<HealthResponse>('/api/health')
  },

  submitCase(payload: CaseFormValues): Promise<CaseSubmitResponse> {
    return request<CaseSubmitResponse>('/api/cases', {
      method: 'POST',
      body: JSON.stringify({ request: payload }),
    })
  },

  caseStatus(threadId: string): Promise<CaseStatusResponse> {
    return request<CaseStatusResponse>(`/api/cases/${encodeURIComponent(threadId)}`)
  },

  resumeCase(threadId: string, value: Record<string, unknown>): Promise<CaseStatusResponse> {
    return request<CaseStatusResponse>(`/api/cases/${encodeURIComponent(threadId)}/resume`, {
      method: 'POST',
      body: JSON.stringify({ value }),
    })
  },

  caseEvents(threadId: string): Promise<AuditEvent[]> {
    return request<AuditEvent[]>(`/api/cases/${encodeURIComponent(threadId)}/events`)
  },

  caseDrafts(threadId: string): Promise<string[]> {
    return request<string[]>(`/api/cases/${encodeURIComponent(threadId)}/drafts`)
  },

  draftContent(draftName: string): Promise<string> {
    return request<string>(`/api/drafts/${encodeURIComponent(draftName)}`)
  },

  supervisorRoute(input: {
    request_text: string
    role: string
    department: string
    available_workers: string[]
  }): Promise<SupervisorDecision> {
    const params = new URLSearchParams({
      request_text: input.request_text,
      role: input.role,
      department: input.department,
      available_workers: input.available_workers.join(','),
    })
    return request<SupervisorDecision>(`/api/supervisor/route?${params.toString()}`, {
      method: 'POST',
    })
  },
}

export function outcomeStatusLabel(outcome: OnboardingOutcome | null): string {
  if (!outcome) return 'In progress'
  return outcome.status === 'completed' ? 'Completed' : 'Rejected'
}
