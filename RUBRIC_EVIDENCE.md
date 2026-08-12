# 100-point rubric evidence map

This file distinguishes implemented code from evidence that must be generated with the team’s live
keys. Do not replace missing live evidence with offline output or fabricated observations.

## 1. Agent fundamentals — 15 points

Implemented:

- `StructuredOutputSupervisor` uses `with_structured_output(SupervisorDecision)`.
- Three live specialists use `create_agent`.
- Specialists receive a real semantic-retrieval tool.
- IT tickets write to SQLite; Jinja2 produces real draft files.
- Pydantic validates boundary, routes, worker results, and approval.

Capture:

- Live LangSmith trace showing specialist retrieval-tool calls.
- `live-routing` typed destinations/reasons.
- SQLite ticket and generated draft paths from `live-full`.

Common failure prevented: tools do not merely ignore arguments and return hardcoded success text.

## 2. Multi-agent/routing architecture — 15 points

Declared choice: **Track A — Supervisor + Workers**.

Implemented:

- Dedicated supervisor with constrained destinations.
- Training, HR Documents, and IT Provisioning specialists.
- Supervisor correction loop for invalid/premature routing.
- Offline deterministic router is explicitly excluded from grading evidence.

Capture:

```bash
onboardai live-routing
```

Save two requests that reach different workers, including destination and reason.

## 3. RAG pipeline — 15 points

Implemented:

- Markdown/CSV loading into `Document` objects.
- `RecursiveCharacterTextSplitter` with overlap and start indices.
- Hugging Face `all-MiniLM-L6-v2` embeddings for the submitted run.
- `InMemoryVectorStore` indexing and semantic retrieval.
- Source/category/chunk citations.
- Hybrid rationale documented in `ARCHITECTURE.md`.
- Deterministic mandatory retrieval plus optional agentic searches.

Capture:

```bash
onboardai rag-evidence --live-embeddings
onboardai evaluate-rag
```

Do not submit the hash-embedding test double as the embedding-model evidence.

## 4. Context and state management — 15 points

Implemented:

- `SqliteSaver` for live workflow checkpoints.
- Unique `thread_id` per onboarding case run.
- Same thread resumes after missing-information and approval interrupts.
- Separate LangGraph `InMemoryStore` for safe cross-thread facts.
- Store is passed separately to `@entrypoint`.

Capture:

```bash
onboardai memory-evidence
onboardai live-full --case-index 0
```

State clearly: the Store crosses thread IDs, while `InMemoryStore` does not survive a process
restart. Production would use `PostgresStore`.

## 5. Human-in-the-loop — 10 points

Implemented:

- Missing start date triggers a user-fixable `interrupt()`.
- All cases trigger approval before consequential action.
- `ApprovalDecision` validates resume input.
- `Command(resume=...)` completes or rejects the same thread.

Capture the visible PAUSED and RESUMED sections from:

```bash
onboardai live-full --case-index 2
```

## 6. Functional API and error handling — 15 points

Implemented:

- Workflow uses `@entrypoint` and nine named `@task`s.
- Real `RetryPolicy` on the draft IT ticket task.
- Simulated first-attempt transient failure.
- Supervisor LLM-recoverable correction feedback.
- User-fixable missing-information interrupt.
- Unexpected errors intentionally propagate.

Capture:

```bash
onboardai live-full --case-index 0 --simulate-it-failure
```

The console must show attempt `#1`, the simulated error, and attempt `#2`.

## 7. Workflow pattern — 10 points

Named pattern: **Orchestrator-Worker**.

Justification: the overall task spans three distinct domains whose tools, prompts, and validation
rules should not be placed in one agent. The supervisor maintains a single delegation point and
combines specialist results before human review.

Point to `agents.py`, `workflow.py`, and the routing log in a full run.

## 8. LangSmith observability — 5 points

Implemented:

- Current `LANGSMITH_TRACING` and course `LANGCHAIN_TRACING_V2` flags.
- Dedicated `LANGSMITH_PROJECT`.
- Key validation command.
- Functional tasks create an inspectable tree.
- Evaluation dataset helper in `evaluation.py`.

Capture:

```bash
onboardai langsmith-check
onboardai live-full --case-index 0 --simulate-it-failure
```

After opening the trace, write three factual sentences:

1. Which task/LLM call dominated latency and its measured duration.
2. Total tokens/cost shown by the trace.
3. One change motivated by the observed trace.

## Repository/documentation requirements

- [x] Clear project description and execution instructions
- [x] Architecture and design rationale
- [x] Security/privacy documentation
- [x] `.gitignore` and empty `.env.example`
- [x] Synthetic data
- [x] Automated tests
- [ ] Team names entered in `SUBMISSION_INFO.md`
- [ ] Programme/cohort dates entered
- [ ] Repository initialized and meaningful incremental commits created by the team
- [ ] Live outputs saved in notebook
- [ ] LangSmith findings written from the real trace
- [ ] Secret-history scan completed

## Final honesty check

- Restart the notebook kernel and run top-to-bottom.
- Do not call offline routing “LLM routing.”
- Do not claim the Store survives process restart.
- Do not claim a document was sent—the project only creates drafts.
- Do not claim LangSmith findings that are not visible in your trace.
- Remove all submission-information placeholders before grading.
