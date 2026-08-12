# 100-point rubric evidence map

The project is intentionally arranged around the eight sections in the course capstone-prep page.

## 1. Agent fundamentals — 15 points

- Live specialist agents are built with `create_agent`.
- Each specialist has a genuine semantic-retrieval tool that uses its query/category arguments.
- The notebook prints the **actual model tool-call name and arguments** from the agent messages.
- The supervisor, routing decision, worker result, synthesis result, and approval boundary use
  Pydantic contracts; model results parsed by Python use structured output.

## 2. Multi-agent / routing architecture — 15 points

**Declared track: Track A — Supervisor + Workers.**

- A dedicated LLM supervisor plans/delegates.
- Training, HR Documents, and IT Provisioning agents are isolated specialists.
- A separate routing-evidence cell gives the LLM all three worker choices and changes only the
  natural-language intent, proving semantic model routing rather than keyword `if` statements.

## 3. RAG pipeline — 15 points

The notebook prints real evidence for:

**load → split → embed → store → retrieve**

The submitted embedding run uses Hugging Face
`sentence-transformers/all-mpnet-base-v2` with `InMemoryVectorStore`.
Retrieval smoke tests ask questions whose expected terms are explicitly present in the source
files. The design is **Hybrid RAG**: mandatory evidence is retrieved deterministically and the
specialist agents can also make contextual retrieval tool calls.

## 4. Context & state management — 15 points

- Main workflow: SQLite `SqliteSaver` with explicit `thread_id`.
- Long-term facts: separate LangGraph Store.
- The notebook runs a genuine `thread-A` workflow invocation that writes a preference, then a
  completely separate `thread-B` invocation that reads it back.

## 5. Human-in-the-loop — 10 points

- Missing required data uses `interrupt()` for a user-fixable pause.
- Final approval uses another real `interrupt()` immediately before consequential finalization.
- The notebook contains separate pause and `Command(resume=...)` cells and saves both outputs.

## 6. Functional API & error handling — 15 points

- Main workflow uses `@task` and `@entrypoint`; no `StateGraph` is used.
- Strategy 1: transient IT failure handled by a real `RetryPolicy`, with printed attempt #1 and #2.
- Strategy 2: missing start date handled by `interrupt()` + `Command(resume=...)`.
- The supervisor planner also contains an LLM-recoverable structured-plan correction loop.
- Unexpected errors are allowed to surface rather than being swallowed.

## 7. Workflow pattern — 10 points

**Named pattern: Orchestrator-Worker.**

The supervisor creates a dynamic `SupervisorPlan`, selected workers execute, and a structured
synthesizer combines the completed worker results. This directly matches the course pattern:
break down → delegate → synthesize.

## 8. LangSmith observability — 5 points

- Exact course flag: `LANGCHAIN_TRACING_V2="true"`.
- LangSmith key is verified before the live demo.
- The final notebook queries actual recent runs and prints a trace-derived observation such as
  the slowest inspected run and any run with an error flag. No latency/cost figures are hardcoded.

## Repository/documentation requirements

- Clear README and execution instructions.
- Architecture, rubric map, security notes, and final run checklist.
- Synthetic data only.
- `.gitignore` excludes secrets/generated artifacts/model cache.
- Programme name, cohort dates, team names, declared track, workflow pattern, and SDAIA Academy
  GitHub link are included.
- The remaining user-owned repository requirement is to push with meaningful incremental commits;
  the suggested commit sequence is in the README.
