"""HTTP API layer that exposes the existing OnboardAI workflow."""

from .main import OnboardAIService, configure_service, create_app, router
from .schemas import (
    ApprovalDecision,
    CaseSubmitRequest,
    CaseSubmitResponse,
    HealthResponse,
    InterruptPayload,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ResumeRequest,
    ResumeResponse,
)
from .service import (
    CaseNotFoundError,
    WorkflowExecutionError,
)
from .service import (
    OnboardAIService as Service,
)

__all__ = [
    "ApprovalDecision",
    "CaseNotFoundError",
    "CaseSubmitRequest",
    "CaseSubmitResponse",
    "HealthResponse",
    "InterruptPayload",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResponse",
    "OnboardAIService",
    "ResumeRequest",
    "ResumeResponse",
    "Service",
    "WorkflowExecutionError",
    "configure_service",
    "create_app",
    "router",
]
