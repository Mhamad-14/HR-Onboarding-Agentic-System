// TypeScript mirrors of the OnboardAI FastAPI contracts.
// See src/onboardai/api/schemas.py and src/onboardai/schemas.py in the backend.

export type WorkerName = 'training' | 'hr_documents' | 'it_provisioning'

export type RouteDestination = WorkerName

export type InterruptType = 'missing_information' | 'human_approval'

export type ApprovalDecision = {
  approved: boolean
  reviewer: string
  comments: string
  approved_actions: WorkerName[]
}

export type Citation = {
  source: string
  category: 'policy' | 'role' | 'training'
  excerpt: string
}

export type WorkerResult = {
  worker: WorkerName
  summary: string
  recommendations: string[]
  artifacts: string[]
  citations: Citation[]
  risk_flags: string[]
  structured_data: Record<string, unknown>
}

export type WorkerAssignment = {
  worker: WorkerName
  objective: string
}

export type SupervisorPlan = {
  assignments: WorkerAssignment[]
  rationale: string
}

export type SynthesisResult = {
  summary: string
  completed_workers: WorkerName[]
  key_risks: string[]
  source_count: number
}

export type OnboardingOutcome = {
  status: 'completed' | 'rejected'
  case_id: string
  employee_id: string
  supervisor_plan: SupervisorPlan
  worker_results: Partial<Record<WorkerName, WorkerResult>>
  synthesis: SynthesisResult
  approval: ApprovalDecision | null
  final_actions: string[]
}

export type InterruptPayload = {
  type: InterruptType
  value: Record<string, unknown> & {
    case_id?: string
    field?: string
    message?: string
    start_date?: string
    employee_id?: string
    proposed_actions?: WorkerName[]
    risk_flags?: string[]
    synthesis?: SynthesisResult
    draft_paths?: string[]
    remembered_preferences?: Record<string, string>
  }
}

export type CaseSubmitResponse = {
  thread_id: string
  interrupt: InterruptPayload | null
  outcome: OnboardingOutcome | null
}

export type CaseStatusResponse = CaseSubmitResponse

export type HealthResponse = {
  status: 'ok'
  mode: 'live' | 'offline'
  embedding_model: string
  vector_store: string
  knowledge_documents: number
  knowledge_chunks: number
  checkpoint_persistence: 'sqlite' | 'memory'
  langsmith_tracing_enabled: boolean
}

export type AuditEvent = {
  event_id: number
  case_id: string
  event_type: string
  payload: Record<string, unknown>
  created_at: string
}

export type SupervisorDecision = {
  destination: RouteDestination
  reason: string
  confidence: 'high' | 'low'
}

export type CaseFormValues = {
  case_id: string
  employee_id: string
  employee_name: string
  role: string
  department: string
  manager_email: string
  start_date: string
  resume_text: string
  request_text: string
  requested_actions: WorkerName[]
  preferred_language: 'English' | 'Arabic'
  training_format: 'online' | 'in_person' | 'hybrid'
}

export const WORKER_META: Record<WorkerName, { label: string; icon: string; tone: string }> = {
  training: { label: 'Training Agent', icon: '🎓', tone: 'blue' },
  hr_documents: { label: 'HR Documents Agent', icon: '📄', tone: 'violet' },
  it_provisioning: { label: 'IT Provisioning Agent', icon: '🔐', tone: 'amber' },
}

export const WORKER_ORDER: WorkerName[] = ['training', 'hr_documents', 'it_provisioning']
