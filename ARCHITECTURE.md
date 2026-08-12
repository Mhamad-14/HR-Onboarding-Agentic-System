# Architecture and design rationale

## Why Track A

The central problem is coordination across distinct domains, not merely escalation or choosing a
knowledge base. A dedicated supervisor selects Training, HR Documents, or IT Provisioning and
then combines their work. Human handoff and multi-source retrieval are supporting capabilities.

## Control flow

1. Pydantic rejects malformed or excessive input at the application boundary.
2. Missing `start_date` causes a user-fixable `interrupt()`.
3. The supervisor returns a typed `SupervisorDecision`.
4. A dedicated `@task` executes the selected specialist.
5. Hybrid RAG injects mandatory evidence and exposes optional retrieval as an agent tool.
6. IT planning creates a `DRAFT` SQLite ticket through a retryable task.
7. Jinja2 creates reversible document drafts.
8. `interrupt()` presents the complete proposal and risk flags to an HR reviewer.
9. `Command(resume=...)` either rejects the case or finalizes only approved sandbox actions.
10. An audit event records the reviewer, approved actions, and final outcomes.

## Supervisor correction loop

The supervisor cannot silently route to an unknown worker because its destination is a `Literal`.
The workflow additionally rejects:

- A worker that was not requested
- A worker that already completed
- Premature `complete`
- Early `human_review`

The error is returned as correction feedback and the model routes again. This is an
LLM-recoverable error strategy rather than an unhandled fall-through.

## Hybrid RAG rationale

A fully optional agentic search is unsafe for mandatory policy: the model could skip retrieval.
A fully fixed two-step pipeline is less flexible for résumé-specific skill gaps. OnboardAI therefore
uses:

- **Fixed retrieval:** role, mandatory training, and policy evidence is injected for every worker.
- **Agentic retrieval:** specialists may call the retrieval tool again with contextual queries.

Every citation includes source, category, chunk/row identifier, and excerpt.

## State ownership

| State | Owner | Lifetime |
|---|---|---|
| Workflow progress and interrupts | LangGraph checkpointer | One `thread_id` |
| Employee language/training preference | LangGraph Store | Across thread IDs |
| Draft IT tickets and audit records | SQLite operations DB | Across processes |
| Generated drafts | Ignored runtime directory | Until explicitly removed |

The résumé remains workflow input and is not copied into long-term memory.

## Consequential-action boundary

The live specialists may retrieve and recommend. Before approval they may create only reversible
drafts. The finalizer runs after `Command(resume=...)`, is encapsulated in a task, and is idempotent
where practical so replay does not duplicate the IT ticket.

