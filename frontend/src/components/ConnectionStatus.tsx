import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { HealthResponse } from '../api/types'

type HealthState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string }

export default function ConnectionStatus() {
  const [state, setState] = useState<HealthState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    api
      .health()
      .then((health) => {
        if (!cancelled) setState({ kind: 'ok', health })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const message =
          error instanceof Error
            ? error.message
            : 'Could not reach the OnboardAI backend'
        setState({ kind: 'error', message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (state.kind === 'loading') {
    return (
      <span className="health-pill health-pill--loading" title="Checking backend…">
        <span className="health-pill__dot" />
        Connecting…
      </span>
    )
  }

  if (state.kind === 'error') {
    return (
      <span
        className="health-pill health-pill--err"
        title={`Backend unreachable: ${state.message}`}
      >
        <span className="health-pill__dot" />
        Backend offline
      </span>
    )
  }

  const { health } = state
  return (
    <span
      className="health-pill health-pill--ok"
      title={`${health.embedding_model} · ${health.vector_store} · ${health.knowledge_documents} documents / ${health.knowledge_chunks} chunks · ${health.checkpoint_persistence} checkpoints`}
    >
      <span className="health-pill__dot" />
      {health.mode === 'live' ? 'Live LLM' : 'Offline demo'} · API connected
    </span>
  )
}
