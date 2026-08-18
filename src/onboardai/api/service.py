"""Service layer that connects the FastAPI endpoints to the real OnboardAI workflow.

This module deliberately contains no AI logic, no mock responses, and no copy of the
workflow. It only:

- builds the existing ``OnboardAIApp`` via ``build_app``,
- maps a client request to a LangGraph ``thread_id``,
- invokes the real ``app.workflow`` entrypoint,
- normalizes LangGraph ``interrupt()`` values into a JSON-friendly envelope,
- resumes paused threads with ``Command(resume=...)`` on the same ``thread_id``.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from langgraph.types import Command

from ..app import OnboardAIApp, build_app
from ..config import langsmith_status
from ..schemas import OnboardingRequest, SupervisorDecision
from .schemas import (
    CaseSubmitRequest,
    CaseSubmitResponse,
    InterruptPayload,
    KnowledgeSearchResponse,
    ResumeResponse,
)


class CaseNotFoundError(LookupError):
    """Raised when the requested thread_id has no active workflow state."""


class WorkflowExecutionError(RuntimeError):
    """Raised when the real workflow raises during submission or resume."""


def _interrupt_value(result: dict) -> dict[str, Any] | None:
    """Return the first LangGraph interrupt value as a plain dict, if any."""

    interrupts = result.get("__interrupt__") or ()
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    if not isinstance(value, dict):
        raise WorkflowExecutionError(
            f"Unexpected interrupt value of type {type(value).__name__}; expected a dict"
        )
    return value


def _case_payload(result: dict) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Split a workflow result into (interrupt_payload, outcome_payload).

    A result may contain an ``__interrupt__`` marker (the workflow is paused and the
    returned dict holds no case data yet) or a final outcome dict (the workflow
    finished and the dict is the ``OnboardingOutcome``).
    """

    interrupt_value = _interrupt_value(result)
    if interrupt_value is not None:
        return interrupt_value, None
    return None, result


@dataclass
class OnboardAIService:
    """Adapter over one ``OnboardAIApp`` instance.

    The same app (and therefore the same SQLite checkpointer, knowledge base, and
    operations database) is shared by all requests. Only the ``thread_id`` differs
    per case.

    ``_thread_meta`` records the case_id and draft paths when a case starts, so
    the events/drafts endpoints keep working after the thread completes (the
    functional-API checkpoint no longer exposes the input once finished).
    """

    app: OnboardAIApp
    mode: str
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _thread_meta: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        live: bool = False,
        persistent: bool = True,
        settings: Any | None = None,
    ) -> OnboardAIService:
        app = build_app(live=live, persistent=persistent, settings=settings)
        return cls(app=app, mode="live" if live else "offline")

    def close(self) -> None:
        self.app.close()

    # ------------------------------------------------------------------ helpers

    def _config(self, thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}

    def _start(self, thread_id: str, request: OnboardingRequest) -> CaseSubmitResponse:
        try:
            result = self.app.workflow.invoke(
                request.model_dump(mode="json"),
                config=self._config(thread_id),
            )
        except Exception as exc:
            raise WorkflowExecutionError(
                f"Workflow failed to start for thread {thread_id!r}: {exc}"
            ) from exc

        interrupt_value, outcome = _case_payload(result)
        if interrupt_value is not None:
            self._thread_meta[thread_id] = {
                "case_id": interrupt_value.get("case_id"),
                "draft_paths": interrupt_value.get("draft_paths", []),
            }
            return CaseSubmitResponse(
                thread_id=thread_id,
                interrupt=InterruptPayload(
                    type=interrupt_value["type"],
                    value=interrupt_value,
                ),
            )
        return CaseSubmitResponse(thread_id=thread_id, outcome=outcome)

    def _resume(self, thread_id: str, resume_value: dict[str, Any]) -> ResumeResponse:
        try:
            result = self.app.workflow.invoke(
                Command(resume=resume_value),
                config=self._config(thread_id),
            )
        except Exception as exc:
            raise WorkflowExecutionError(
                f"Workflow failed to resume for thread {thread_id!r}: {exc}"
            ) from exc

        interrupt_value, outcome = _case_payload(result)
        if outcome is not None:
            self._thread_meta.setdefault(thread_id, {})["outcome"] = outcome
        if interrupt_value is not None:
            return ResumeResponse(
                thread_id=thread_id,
                interrupt=InterruptPayload(
                    type=interrupt_value["type"],
                    value=interrupt_value,
                ),
            )
        return ResumeResponse(thread_id=thread_id, outcome=outcome)

    # ------------------------------------------------------------------ public

    def submit_case(self, payload: CaseSubmitRequest) -> CaseSubmitResponse:
        thread_id = payload.thread_id or f"{payload.request.case_id}-{uuid.uuid4().hex[:8]}"
        with self._lock:
            return self._start(thread_id, payload.request)

    def resume_case(self, thread_id: str, resume_value: dict[str, Any]) -> ResumeResponse:
        with self._lock:
            return self._resume(thread_id, resume_value)

    def case_status(self, thread_id: str) -> ResumeResponse:
        """Return the current state of a thread without resuming or mutating it."""

        config = self._config(thread_id)
        state = self.app.workflow.get_state(config)

        final_outcome = self._thread_meta.get(thread_id, {}).get("outcome")
        if not state.interrupts and final_outcome is not None:
            return ResumeResponse(
                thread_id=thread_id,
                outcome=final_outcome,
            )

        if state.interrupts:
            interrupt_value = state.interrupts[0].value

            if not isinstance(interrupt_value, dict):
                raise WorkflowExecutionError(
                    f"Unexpected interrupt value of type "
                    f"{type(interrupt_value).__name__}; expected a dict"
                )

            return ResumeResponse(
                thread_id=thread_id,
                interrupt=InterruptPayload(
                    type=interrupt_value["type"],
                    value=interrupt_value,
                ),
            )

        for snapshot in self.app.workflow.get_state_history(config, limit=50):
            if not snapshot.interrupts:
                continue

            interrupt_value = snapshot.interrupts[0].value

            if not isinstance(interrupt_value, dict):
                continue

            return ResumeResponse(
                thread_id=thread_id,
                interrupt=InterruptPayload(
                    type=interrupt_value["type"],
                    value=interrupt_value,
                ),
            )

        raise CaseNotFoundError(
            f"No workflow state found for thread {thread_id!r}"
        )

    def thread_case_id(self, thread_id: str) -> str:
        """Return the case_id recorded for this thread.

        The registry populated at submit time is authoritative: it works for both
        paused and completed threads. For a paused thread the checkpoint interrupt
        payload is used as a fallback so restarted processes (fresh registry)
        still resolve the case_id.
        """

        meta = self._thread_meta.get(thread_id)
        if meta and isinstance(meta.get("case_id"), str):
            return meta["case_id"]

        state = self.app.workflow.get_state(self._config(thread_id))
        for interrupt in getattr(state, "interrupts", ()) or ():
            value = getattr(interrupt, "value", interrupt)
            if isinstance(value, dict) and isinstance(value.get("case_id"), str):
                return value["case_id"]

        raise CaseNotFoundError(f"No case_id found for thread {thread_id!r}")

    def route_once(
        self,
        *,
        request_text: str,
        role: str,
        department: str,
        available_workers: list[str],
    ) -> SupervisorDecision:
        try:
            return self.app.services.supervisor.route_once(
                request_text=request_text,
                role=role,
                department=department,
                available_workers=available_workers,
            )
        except Exception as exc:
            raise WorkflowExecutionError(f"Supervisor routing failed: {exc}") from exc

    def case_events(self, case_id: str) -> list[dict[str, Any]]:
        return self.app.services.operations.list_events(case_id)

    def case_drafts(self, case_id: str) -> list[str]:
        drafts_dir = self.app.services.renderer.output_dir
        if not drafts_dir.exists():
            return []
        return sorted(
            str(path)
            for path in drafts_dir.glob(f"{case_id}*")
            if path.is_file()
        )

    def draft_content(self, draft_path: str) -> str:
        path = self.app.services.renderer.output_dir / draft_path
        if not path.is_file():
            raise CaseNotFoundError(f"No draft file found: {draft_path}")
        return path.read_text(encoding="utf-8")

    def search_knowledge(
        self,
        *,
        query: str,
        categories: list[str] | None = None,
        k: int = 5,
    ) -> KnowledgeSearchResponse:
        citations = self.app.knowledge.search(query, categories=categories, k=k)
        return KnowledgeSearchResponse(
            query=query,
            citations=[citation.model_dump(mode="json") for citation in citations],
            embedding_model=self.app.knowledge.embedding_label,
        )

    def health(self) -> dict[str, Any]:
        knowledge = self.app.knowledge
        status = langsmith_status()
        return {
            "status": "ok",
            "mode": self.mode,
            "embedding_model": knowledge.embedding_label,
            "vector_store": type(knowledge.vector_store).__name__,
            "knowledge_documents": len(knowledge.raw_documents),
            "knowledge_chunks": len(knowledge.chunks),
            "checkpoint_persistence": "sqlite",
            "langsmith_tracing_enabled": bool(
                status.get("api_key_present") and status.get("course_tracing_flag")
            ),
        }
