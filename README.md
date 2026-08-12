# OnboardAI

Human-supervised HR onboarding orchestration using LangChain, LangGraph, Hybrid RAG, durable checkpoints, and a Track A Supervisor + Workers architecture.

> Academic capstone project. The system uses synthetic employee data and operates after an employee has been marked as hired. It does not make hiring, salary, termination, or legal decisions.

---

## Project Overview

OnboardAI is a human-supervised multi-agent HR onboarding system designed to coordinate post-hire onboarding activities.

The system uses a structured LLM supervisor to select the appropriate specialist worker for each requested onboarding task.

The project includes three specialist workers:

1. **Training Agent**
   - Compares job-relevant resume skills with approved role requirements.
   - Retrieves approved training courses.
   - Produces a cited 30/60/90-day training plan.

2. **HR Documents Agent**
   - Retrieves approved onboarding and data-minimization policies.
   - Prepares reversible HR document drafts.
   - Keeps generated documents in draft/review status rather than sending them externally.

3. **IT Provisioning Agent**
   - Retrieves the approved role-to-access matrix.
   - Creates a sandboxed draft IT ticket.
   - Flags privileged access for additional human approval.

The supervisor coordinates these specialists and determines which worker should run next.

---

## Programme Information

- **Training Programme:** Building AI Agent Systems
- **Cohort Dates:** 9 August 2026 – 13 August 2026
- **Instructor:** Mohammad Albeladi
- **Declared Track:** Track A — Supervisor + Workers
- **Workflow Pattern:** Orchestrator-Worker
- **RAG Architecture:** Hybrid RAG

### Team

The project was completed collaboratively by:

- Aleen Alfawzan
- Fadwa Nasser Aldukhi
- Reem Almehize
- Noura Almuqbil
- Moudi Alhomoud

SDAIA Academy GitHub:

https://github.com/SDAIAAcademy

---

## Architecture

The project follows the **Track A — Supervisor + Workers** architecture.

The supervisor uses an LLM with structured output to select exactly one unfinished specialist worker.

The available workers are:

- Training
- HR Documents
- IT Provisioning

The supervisor is implemented using a Pydantic structured-output contract rather than keyword-based routing.

### Workflow

```text
Synthetic hired-employee event
            |
            v
   Boundary validation
            |
            v
   Onboarding Coordinator
            |
            v
 Structured LLM Supervisor
       /       |       \
      /        |        \
     v         v         v
Training    HR Docs    IT Provisioning
     \         |         /
      \        |        /
       v       v       v
          Hybrid RAG
              |
              v
 Approved HR knowledge base
              |
              v
      Drafts + proposed actions
              |
              v
      Human approval interrupt
              |
              v
       Command(resume)
              |
              v
     Approved sandbox actions
              |
              v
        Audit event
```

---

## Workflow Pattern

### Orchestrator-Worker

The named workflow pattern is **Orchestrator-Worker**.

The supervisor acts as the orchestrator and selects the appropriate specialist worker based on the onboarding request and the workers that have already completed.

Each worker is responsible for a specialized domain, while the supervisor coordinates the overall workflow.

This pattern fits HR onboarding because onboarding contains several independent but related domains such as training, HR documentation, and IT provisioning.

---

## Agent Design

### Supervisor

The supervisor receives:

- User request
- Employee role
- Department
- Requested workers
- Completed workers
- Routing feedback

It returns a structured `SupervisorDecision`.

The decision contains:

- Destination
- Reason
- Confidence

The live supervisor uses:

```text
LLM
  |
  v
with_structured_output(...)
  |
  v
SupervisorDecision
```

The repository also contains an offline deterministic supervisor for testing. This test adapter is explicitly not used as evidence of LLM-based routing.

---

## Specialist Workers

### Training Worker

The Training Worker searches the approved knowledge base before generating its result.

It retrieves:

- Role requirements
- Training catalogue
- Relevant HR policies

It compares job-relevant resume skills with approved requirements and produces a structured 30/60/90-day training plan.

The worker is instructed not to infer protected characteristics or invent courses.

### HR Documents Worker

The HR Documents Worker retrieves approved onboarding and data-minimization policies.

It prepares:

- Manager welcome notification drafts
- Onboarding checklist
- Review steps

Generated documents remain drafts and are not represented as externally sent or legally approved documents.

### IT Provisioning Worker

The IT Provisioning Worker retrieves the exact role-to-access row and security policy.

It:

- Identifies required access
- Flags privileged access
- Creates a draft IT request
- Requires human approval before consequential actions

The worker does not activate accounts or independently approve access.

---

# RAG Architecture

## Hybrid RAG

OnboardAI uses a **Hybrid RAG** architecture.

The system combines:

1. **Fixed retrieval**
   - Mandatory role, training, and policy evidence is retrieved for every specialist.

2. **Agentic retrieval**
   - Specialist agents can use an approved retrieval tool for additional contextual searches.

3. **Citations**
   - Retrieved evidence includes sources and excerpts so that recommendations can be traced back to the approved knowledge base.

The implementation explicitly combines mandatory retrieved context with a model-accessible retrieval tool.

### Why Hybrid RAG?

A pure 2-Step RAG approach would provide predictable retrieval but less flexibility for context-specific searches.

A fully Agentic RAG approach could allow the model to decide when to retrieve information, but mandatory HR and security evidence should not depend entirely on optional retrieval.

Hybrid RAG provides both:

- predictable mandatory evidence
- flexible contextual retrieval

---

# LangGraph Functional API

The workflow uses the LangGraph Functional API.

The implementation uses:

- `@task`
- `@entrypoint`

Tasks are used for individual workflow operations, while the entrypoint defines the durable onboarding workflow.

---

## Reliability and Error Handling

### RetryPolicy

The IT ticket creation task uses LangGraph `RetryPolicy`.

The configuration allows transient IT failures to be retried automatically.

The workflow uses:

```text
RetryPolicy
    |
    v
Attempt 1
    |
 transient failure
    |
    v
Attempt 2
    |
    v
Success
```

The implementation configures up to three attempts and retries specifically on `TransientITError`.

### Human-in-the-loop

The workflow pauses before consequential actions using:

```text
interrupt()
```

The human reviews:

- Proposed actions
- Risk flags
- Draft paths
- Remembered preferences

The workflow then continues using a resume operation after the human provides an approval decision.

---

# Persistence and Memory

OnboardAI separates short-term workflow state from long-term employee preferences.

### Short-term state

LangGraph uses a checkpointer with a `thread_id` so that a workflow can pause and resume.

### Long-term Store

A separate Store is used for safe cross-thread preferences.

This means conversation history does not automatically become long-term memory.

The workflow connects the durable entrypoint to both a checkpointer and a separate Store.

---

# Human Approval

Human approval is required before consequential actions.

The workflow generates drafts and proposed actions first.

It then pauses with:

```text
interrupt()
```

The human reviews the proposed actions and either approves or rejects them.

When approved, the workflow finalizes only the approved actions and records an audit event.

---

# Safety Boundaries

The project is designed with the following safety boundaries:

- Synthetic employee profiles only.
- No protected-characteristic inference.
- No hiring decisions.
- No compensation decisions.
- No termination decisions.
- No legal decisions.
- HR documents remain drafts until human review.
- Privileged access is flagged.
- Consequential actions require human approval.
- Retrieved knowledge is treated as approved reference data.
- API keys are loaded through environment variables or secure notebook secrets.
- The offline supervisor is not presented as LLM-routing evidence.

---

# Installation

## Requirements

- Python 3.11–3.13
- Groq API key for live agent execution
- LangSmith API key for observability
- Internet access for the first Hugging Face embedding-model download

## Install

```bash
python3 -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install the project:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

---

# Environment Variables

Create a `.env` file locally.

Never commit API keys to GitHub.

Example:

```text
GROQ_API_KEY=your_key_here
LANGSMITH_API_KEY=your_key_here
LANGSMITH_PROJECT=onboardai-capstone
LANGSMITH_TRACING=true
LANGCHAIN_TRACING_V2=true
ONBOARDAI_EMBEDDINGS=huggingface
```

---

# Running the Project

## 1. Automated verification

```bash
pytest
```

Run linting:

```bash
ruff check src tests
```

Run RAG evaluation:

```bash
onboardai evaluate-rag
```

---

## 2. Live RAG Evidence

Run:

```bash
onboardai rag-evidence --live-embeddings
```

This demonstrates the live Hugging Face embedding pipeline and retrieval evidence.

---

## 3. Live Supervisor Routing

Run:

```bash
onboardai live-routing
```

The live routing evidence should demonstrate different destinations, reasons, and confidence values.

The live supervisor uses structured LLM output rather than keyword matching.

---

## 4. Full Live Workflow

Run:

```bash
onboardai live-full --case-index 0 --simulate-it-failure
```

Expected evidence includes:

- Live supervisor decisions
- Specialist execution
- Retrieval citations
- IT retry behavior
- Human approval interrupt
- Workflow resume
- Generated Jinja2 drafts
- SQLite audit event

---

## 5. Missing Information Case

Case 2 demonstrates a missing-information interrupt:

```bash
onboardai live-full --case-index 2
```

The workflow requests the missing start date before continuing.

---

## 6. Cross-thread Memory Evidence

Run:

```bash
onboardai memory-evidence
```

This demonstrates that a safe preference written under one thread can be recalled from a different thread using the separate Store.

---

## 7. LangSmith Verification

Run:

```bash
onboardai langsmith-check
```

Then inspect the live workflow trace.

The trace can be used to evaluate:

- Latency
- Token usage
- Cost
- Tool calls
- Retry behavior
- Workflow execution

---

# Offline Mode

The project also provides an offline workflow for testing:

```bash
onboardai offline-full --case-index 0 --simulate-it-failure
```

Offline mode is useful for development and integration tests.

However, its deterministic supervisor is a test adapter and must not be used as evidence of model-driven Track A routing.

---

# Project Structure

```text
OnboardAI/
│
├── src/
│   └── onboardai/
│       ├── agents.py
│       ├── app.py
│       ├── config.py
│       ├── demo.py
│       ├── documents.py
│       ├── evaluation.py
│       ├── rag.py
│       ├── schemas.py
│       ├── storage.py
│       └── workflow.py
│
├── data/
│   ├── knowledge/
│   └── templates/
│
├── tests/
│
├── notebooks/
│
├── runtime/
│
├── ARCHITECTURE.md
├── SECURITY.md
├── RUBRIC_EVIDENCE.md
├── SUBMISSION_INFO.md
├── VERIFICATION.md
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

# Rubric Coverage

The project is designed around the eight capstone rubric sections.

| Rubric Section             | OnboardAI Evidence                                          |
| --------------------------- | ------------------------------------------------------------ |
| 1. Agent Fundamentals      | Real specialist tool calls and structured Pydantic outputs  |
| 2. Multi-Agent / Routing   | LLM-based structured supervisor                             |
| 3. RAG Pipeline            | Documents, embeddings, retrieval, citations, Hybrid RAG     |
| 4. Context & State         | Checkpointer + separate Store + cross-thread memory         |
| 5. Human-in-the-loop       | `interrupt()` + resume approval                             |
| 6. LangGraph & Reliability | `@task`, `@entrypoint`, `RetryPolicy`, error handling        |
| 7. Workflow Pattern        | Orchestrator-Worker                                          |
| 8. LangSmith               | Workflow tracing and execution observability                 |

---

# Documentation

Additional technical documentation:

- `ARCHITECTURE.md` — system architecture and responsibilities
- `SECURITY.md` — safety boundaries and threat model
- `RUBRIC_EVIDENCE.md` — rubric mapping and evidence
- `SUBMISSION_INFO.md` — project and programme information
- `VERIFICATION.md` — verification results

---

# Limitations

This is an academic capstone project using synthetic data.

It is not intended to:

- make employment decisions
- make legal decisions
- automatically grant privileged access
- send HR communications without review
- replace human approval for consequential actions

---

# Course References

- SDAIA Academy GitHub:
  https://github.com/SDAIAAcademy

- Course — Supervisor, Handoffs, and Multi-Source Routing:
  https://mohammadyusif.github.io/agentic-ai-systems/L01/08b_supervisor_and_handoffs.html

- Course — Capstone Prep:
  https://mohammadyusif.github.io/agentic-ai-systems/L01/capstone_prep.html

- LangGraph Functional API:
  https://docs.langchain.com/oss/python/langgraph/functional-api

- LangChain Structured Output:
  https://docs.langchain.com/oss/python/langchain/structured-output

- LangSmith Observability:
  https://docs.langchain.com/langsmith/observability-quickstart
