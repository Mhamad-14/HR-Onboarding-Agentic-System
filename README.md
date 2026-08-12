# OnboardAI — Human-Supervised HR Onboarding Orchestrator

**Team:** Aleen Alfawzan · Fadwa Nasser Aldukhi · Reem Almehize · Noura Almuqbil · Moudi Alhomoud
**Training programme:** Building Agentic AI Systems — SDAIA Academy  
**Cohort/session dates:** 9 August 2026 — 13 August 2026  
**Declared capstone track:** **Track A — Supervisor + Workers**  
**Named workflow pattern:** **Orchestrator-Worker**  
**RAG architecture:** **Hybrid RAG**

OnboardAI is a human-supervised, post-hire onboarding system. A dedicated HR Supervisor LLM
decomposes an onboarding request and delegates to three specialist agents:

1. **Training Agent** — skill-gap reasoning and approved training recommendations.
2. **HR Documents Agent** — policy-grounded reversible onboarding drafts.
3. **IT Provisioning Agent** — least-privilege access planning and a sandbox SQLite draft ticket.

The worker outputs are deterministically checked against approved HR data, synthesized, and then
paused for human approval before consequential finalization.

## Why this final version

This project combines the strongest parts of two earlier approaches:

- a clean Python package, tests, synthetic knowledge base, Jinja2 documents, SQLite operations,
  and Hybrid RAG;
- a rubric-first Colab notebook with explicit tool-call evidence, true cross-thread Store evidence,
  separate pause/resume cells, grounding validation, a real Orchestrator-Worker synthesizer, and
  dynamic LangSmith observations.

## Course alignment

The code mirrors the course topics directly:

- LangChain tool-using agents
- Pydantic structured output
- Track A Supervisor + Workers
- Retrieval, embeddings, semantic search, and RAG agents
- LangGraph `@task` / `@entrypoint`
- `SqliteSaver` short-term state and a separate Store
- `interrupt()` / `Command(resume=...)`
- `RetryPolicy`
- Orchestrator-Worker workflow
- LangSmith tracing
- secrets and generated-file hygiene

## RAG design

The project uses **Hybrid RAG**.

Mandatory evidence is retrieved deterministically so role/access/training requirements cannot be
silently skipped. Each specialist agent also receives a real semantic-retrieval tool and is
required to use it for contextual searches.

Final course IDs and access names are validated against the approved CSV source files. This
prevents an LLM from inventing identifiers such as a non-existent training course.

The submitted RAG evidence uses:

- `HuggingFaceEmbeddings`
- `sentence-transformers/all-mpnet-base-v2`
- `RecursiveCharacterTextSplitter`
- `InMemoryVectorStore`

## Colab execution

1. Open `OnboardAI_Final_Capstone.ipynb` in Google Colab.
2. Add these two Colab Secrets and enable notebook access:
   - `GROQ_API_KEY`
   - `LANGSMITH_API_KEY`
3. Run the notebook from top to bottom.
4. If only the notebook is open in Colab, upload `OnboardAI_Final_Submission_V3.zip` when the bootstrap cell prompts you.
5. Keep every output in the saved notebook.

The notebook deliberately verifies the local `onboardai` import after installation, which prevents
the `ModuleNotFoundError: No module named 'onboardai'` problem that occurs when only the notebook
is uploaded.

## Evidence order in the canonical notebook

1. Environment and safe secrets
2. Package/test verification
3. LangSmith key validation
4. Real Hugging Face RAG indexing/retrieval
5. Retrieval smoke tests
6. Live Track A routing
7. Actual model-selected retrieval tool call
8. Real cross-thread Store test
9. User-fixable missing-information pause/resume
10. Full live Orchestrator-Worker run with real `RetryPolicy`
11. Human approval pause
12. Same-thread `Command(resume=...)`
13. Final memory/audit evidence
14. Dynamic LangSmith trace observation
15. Rubric write-up

## Repository structure

```text
OnboardAI_Final_Capstone/
├── OnboardAI_Final_Capstone.ipynb
├── README.md
├── ARCHITECTURE.md
├── RUBRIC_EVIDENCE.md
├── SECURITY.md
├── SUBMISSION_INFO.md
├── FINAL_RUN_CHECKLIST.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── data/
│   ├── knowledge/
│   ├── templates/
│   └── sample_requests.json
├── src/onboardai/
├── tests/
└── runtime/.gitkeep
```

## Rubric Alignment

### 1. Agent Fundamentals — 15 points
OnboardAI uses real LangChain tool-using agents rather than hardcoded responses. Specialist
workers perform genuine retrieval/tool calls using their input request, and structured results
are validated with Pydantic models through `with_structured_output`. The executed notebook
contains visible evidence of the tool calls and structured worker outputs.

### 2. Multi-Agent / Routing Architecture — 15 points
The project implements Track A — Supervisor + Workers. A dedicated Supervisor LLM makes the
routing and delegation decision and assigns work to the Training, HR Documents, and IT
Provisioning specialist agents. The routing is model-driven rather than based on keyword
matching, and the live notebook demonstrates the resulting delegation.

### 3. RAG Pipeline — 15 points
The project uses Hybrid RAG. Documents are loaded, split with
`RecursiveCharacterTextSplitter`, embedded using
`HuggingFaceEmbeddings` with `sentence-transformers/all-mpnet-base-v2`, stored in an
`InMemoryVectorStore`, and retrieved through semantic search. Hybrid RAG was selected because
the onboarding system requires both deterministic retrieval of mandatory HR evidence and
semantic retrieval for contextual specialist-agent searches. The notebook contains retrieval
smoke tests with visible results.

### 4. Context and State Management — 15 points
Short-term conversation state is persisted with LangGraph `SqliteSaver` using a
`thread_id`, while long-term facts are stored separately in a LangGraph Store. The notebook
includes a cross-thread test demonstrating that a fact written in one thread can be retrieved
from a different thread, providing evidence that the information is not merely stored in
short-term conversation state.

### 5. Human-in-the-Loop — 10 points
The workflow uses LangGraph `interrupt()` to pause before consequential onboarding
finalization and requires explicit human approval. The notebook separately demonstrates both
the pause and the continuation using `Command(resume=...)`, with captured output showing that
the workflow successfully resumes and completes.

### 6. LangGraph Functional API and Error Handling — 15 points
The workflow uses LangGraph's Functional API through `@task` and `@entrypoint`. Reliability
is demonstrated through multiple error-handling strategies, including a real `RetryPolicy`
for transient failures and validation/grounding checks for deterministic failure handling.
The executed notebook contains evidence of the reliability behavior rather than relying only
on documentation.

### 7. Workflow Pattern — 10 points
The declared workflow pattern is **Orchestrator-Worker**. The Supervisor/orchestrator
decomposes the onboarding request and delegates independent work to specialist workers before
their results are validated and synthesized. This pattern fits the project because onboarding
naturally consists of several specialist tasks that can be coordinated by a central
orchestrator.

### 8. LangSmith Observability — 5 points
LangSmith tracing is enabled for the live workflow using the required LangSmith tracing
configuration. The notebook validates the LangSmith credentials and observes the executed
workflow dynamically. The captured trace evidence is used to inspect agent/tool activity and
workflow behavior rather than merely enabling tracing without verification.
## Programme Attribution

Completed under **Building Agentic AI Systems**, delivered through **SDAIA Academy**,
9 August 2026 — 13 August 2026.

**SDAIA Academy GitHub:** https://github.com/SDAIAAcademy
