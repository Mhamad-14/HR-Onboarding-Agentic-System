# Architecture

## Declared multi-agent track

**Track A — Supervisor + Workers.**

A dedicated LLM supervisor is the only component that decomposes/delegates work. Specialist
workers do not select one another.

## Explicit workflow pattern

**Orchestrator-Worker.**

The course defines this pattern as an orchestrator that breaks a task into subtasks, delegates
those subtasks to workers, and synthesizes their outputs. OnboardAI implements all three parts:

1. `SupervisorPlan` dynamically creates worker assignments.
2. Training, HR Documents, and IT Provisioning agents execute the assignments.
3. `SynthesisResult` combines the worker outputs before human review.

## Flow

```mermaid
flowchart TD
    A[Synthetic hired employee request] --> B[Pydantic validation]
    B --> C{Missing required info?}
    C -->|Yes| D[interrupt: ask human]
    D -->|Command resume| E[LLM Supervisor / Orchestrator]
    C -->|No| E

    E -->|SupervisorPlan| F[Training Agent]
    E -->|SupervisorPlan| G[HR Documents Agent]
    E -->|SupervisorPlan| H[IT Provisioning Agent]

    K[Approved HR knowledge base] --> R[Hybrid RAG]
    R --> F
    R --> G
    R --> H

    F --> V[Deterministic grounding validation]
    G --> V
    H --> V

    V --> S[Structured LLM Synthesizer]
    S --> J[Jinja2 reversible drafts]
    J --> P[interrupt: HR approval]
    P -->|Command resume approve| X[Finalize sandbox actions]
    P -->|reject| Y[Stop]

    CP[(SQLite SqliteSaver)] --- E
    ST[(Separate LangGraph Store)] --- E
    LS[(LangSmith traces)] --- E
```

## Hybrid RAG

The project deliberately combines:

- **deterministic retrieval** of mandatory role/policy evidence, and
- **agentic retrieval tool calls** chosen by each specialist LLM.

This gives the HR workflow control over mandatory evidence while still allowing contextual
searches, which matches the course distinction between fixed RAG chains and RAG agents.

## State model

- Short-term workflow state: `SqliteSaver`, scoped by `thread_id`.
- Long-term employee preferences/training facts: separate `InMemoryStore`, scoped by employee
  namespace and independent of `thread_id`.
- Production note: `InMemoryStore` crosses threads but does not survive a process restart.
  `PostgresStore` would be the production replacement.

## Consequential-action boundary

Before the IT ticket can move from DRAFT to APPROVED and before approved training facts are
written, the workflow calls `interrupt()`. The same thread must be resumed with
`Command(resume=...)`.
