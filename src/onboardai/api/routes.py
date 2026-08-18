"""FastAPI routes for the OnboardAI dashboard backend.

Every endpoint delegates to :class:`OnboardAIService`, which invokes the real
LangGraph workflow. No AI behavior or mock responses live in this module.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas import SupervisorDecision
from .schemas import (
    CaseSubmitRequest,
    CaseSubmitResponse,
    HealthResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ResumeRequest,
    ResumeResponse,
)
from .service import (
    CaseNotFoundError,
    OnboardAIService,
    WorkflowExecutionError,
)

router = APIRouter(prefix="/api", tags=["onboardai"])

ServiceDependency = Annotated[OnboardAIService, Depends(lambda: get_service())]

_service: OnboardAIService | None = None


def configure_service(service: OnboardAIService) -> None:
    """Install the service instance used by route dependencies (app factory calls this)."""

    global _service
    _service = service


def get_service() -> OnboardAIService:
    if _service is None:
        raise RuntimeError("OnboardAIService has not been configured")
    return _service


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(service: ServiceDependency) -> HealthResponse:
    return HealthResponse(**service.health())


@router.post(
    "/cases",
    response_model=CaseSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_case(
    payload: CaseSubmitRequest,
    service: ServiceDependency,
) -> CaseSubmitResponse:
    try:
        return service.submit_case(payload)
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/cases/{thread_id}/resume", response_model=ResumeResponse)
def resume_case(
    thread_id: str,
    payload: ResumeRequest,
    service: ServiceDependency,
) -> ResumeResponse:
    try:
        return service.resume_case(thread_id, payload.value)
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/cases/{thread_id}", response_model=ResumeResponse)
def case_status(
    thread_id: str,
    service: ServiceDependency,
) -> ResumeResponse:
    """Return the current state of a thread without resuming it.

    For a thread paused at an interrupt this returns the pending interruption
    payload (same shape as the submit response) so the dashboard can refresh the
    approval screen. For a completed thread it returns the last interruption
    payload from the checkpoint history. The thread is never resumed here, so
    polling this endpoint cannot accidentally approve or re-run a case.
    """

    try:
        return service.case_status(thread_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/cases/{thread_id}/events", response_model=list[dict[str, Any]])
def case_events(
    thread_id: str,
    service: ServiceDependency,
) -> list[dict[str, Any]]:
    try:
        case_id = service.thread_case_id(thread_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.case_events(case_id)


@router.get("/cases/{thread_id}/drafts", response_model=list[str])
def case_drafts(
    thread_id: str,
    service: ServiceDependency,
) -> list[str]:
    try:
        case_id = service.thread_case_id(thread_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.case_drafts(case_id)


@router.get("/drafts/{draft_name:path}", response_model=str)
def draft_content(
    draft_name: str,
    service: ServiceDependency,
) -> str:
    try:
        return service.draft_content(draft_name)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
def knowledge_search(
    payload: KnowledgeSearchRequest,
    service: ServiceDependency,
) -> KnowledgeSearchResponse:
    return service.search_knowledge(
        query=payload.query,
        categories=payload.categories,
        k=payload.k,
    )


@router.post("/supervisor/route", response_model=SupervisorDecision)
def supervisor_route(
    service: ServiceDependency,
    request_text: Annotated[str, Query(min_length=5, max_length=2_000)],
    role: Annotated[str, Query(min_length=2, max_length=100)],
    department: Annotated[str, Query(min_length=2, max_length=100)],
    available_workers: Annotated[list[str] | None, Query()] = None,
) -> SupervisorDecision:
    workers = available_workers or ["training", "hr_documents", "it_provisioning"]
    try:
        return service.route_once(
            request_text=request_text,
            role=role,
            department=department,
            available_workers=workers,
        )
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
