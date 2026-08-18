"""HTTP boundary contracts for the OnboardAI REST API.

These models are intentionally thin: they reuse the existing ``onboardai.schemas``
contracts for the request and the final outcome, and add only the HTTP-specific
envelope needed to represent LangGraph ``interrupt()`` pauses.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import (
    ApprovalDecision,
    OnboardingOutcome,
    OnboardingRequest,
    SupervisorDecision,
)

__all__ = [
    "ApprovalDecision",
    "CaseSubmitRequest",
    "CaseSubmitResponse",
    "HealthResponse",
    "InterruptPayload",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResponse",
    "OnboardingOutcome",
    "OnboardingRequest",
    "ResumeRequest",
    "SupervisorDecision",
]


class StrictApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseSubmitRequest(StrictApiModel):
    """Client payload for starting a new onboarding case.

    ``request`` reuses the existing workflow contract so the API cannot drift from
    the Pydantic boundary the LangGraph entrypoint already validates.
    """

    request: OnboardingRequest
    thread_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Optional client-supplied LangGraph thread_id. A server-generated id is used when omitted.",
    )


class InterruptPayload(StrictApiModel):
    """Normalized view of a LangGraph ``interrupt()`` pause.

    The raw interrupt value is a plain dict whose ``type`` is one of
    ``missing_information`` or ``human_approval``. The API keeps the full
    interrupt value so the dashboard can render every field the workflow emits.
    """

    type: Literal["missing_information", "human_approval"]
    value: dict[str, Any]


class CaseSubmitResponse(StrictApiModel):
    """Result of starting a case.

    Exactly one of ``interrupt`` or ``outcome`` is populated:
    - ``interrupt``: the workflow paused and must be resumed with
      ``POST /api/cases/{thread_id}/resume``.
    - ``outcome``: the workflow completed without pausing (not expected for the
      live path, which always pauses for human approval).
    """

    thread_id: str
    interrupt: InterruptPayload | None = None
    outcome: OnboardingOutcome | None = None


class ResumeRequest(StrictApiModel):
    """Payload for resuming a paused thread.

    ``value`` is passed unchanged to ``Command(resume=...)``. For a
    ``missing_information`` pause it must contain ``start_date``; for a
    ``human_approval`` pause it is an ``ApprovalDecision``.
    """

    value: dict[str, Any]


class ResumeResponse(StrictApiModel):
    thread_id: str
    interrupt: InterruptPayload | None = None
    outcome: OnboardingOutcome | None = None


class KnowledgeSearchRequest(StrictApiModel):
    query: str = Field(min_length=3, max_length=500)
    categories: list[Literal["policy", "role", "training"]] | None = None
    k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResponse(StrictApiModel):
    query: str
    citations: list[Any]
    embedding_model: str


class HealthResponse(StrictApiModel):
    status: Literal["ok"]
    mode: Literal["live", "offline"]
    embedding_model: str
    vector_store: str
    knowledge_documents: int
    knowledge_chunks: int
    checkpoint_persistence: Literal["sqlite", "memory"]
    langsmith_tracing_enabled: bool
