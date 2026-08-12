# Verification record

Verified locally on 2026-08-11 with Python 3.13.9.

## Completed checks

- `pytest`: **8 passed**
- `ruff check src tests`: **passed**
- `ruff format --check src tests`: **passed**
- Evidence notebook JSON validation: **passed**
- Offline full workflow: **passed**
  - Three workers completed
  - Real `RetryPolicy` produced attempt #1 failure and attempt #2 success
  - Human-approval interrupt surfaced
  - `Command(resume=...)` completed the same thread
  - SQLite audit event written
- Missing-start-date workflow: **passed**
  - Missing-information interrupt surfaced
  - Date supplied on resume
  - Approval interrupt surfaced
  - Workflow completed
- Retrieval smoke evaluation: **3/3 passed**
- Real Hugging Face `all-MiniLM-L6-v2` indexing/retrieval: **passed**
  - Retrieved Software Engineer role matrix
  - Retrieved `ENG-201` Docker course
  - Retrieved privileged-access approval policy
- Live application composition with current libraries: **passed with a dummy non-network key**
  - `StructuredOutputSupervisor` constructed
  - All three live `create_agent` workers constructed
  - Pydantic route schema exposes only the five implemented destinations

## Deliberately not claimed

No Groq request or LangSmith trace was executed because no user API keys were available. The team
must run the live evidence commands, save their genuine notebook outputs, inspect the trace, and
write observations from that trace. Offline results must not be presented as model-driven routing.

## Verified dependency versions

- LangChain 1.3.14
- LangGraph 1.2.11
- langchain-groq 1.1.3
- langchain-huggingface 1.2.2
- langgraph-checkpoint-sqlite 3.1.1
- LangSmith 0.10.17
- Pydantic 2.13.4
- sentence-transformers 5.7.0

