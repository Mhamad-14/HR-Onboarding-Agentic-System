"""FastAPI application factory for the OnboardAI dashboard backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import configure_service, router
from .service import OnboardAIService

__all__ = ["OnboardAIService", "configure_service", "create_app", "router"]


def create_app(
    *,
    live: bool = False,
    persistent: bool = True,
    service: OnboardAIService | None = None,
) -> FastAPI:
    """Create the FastAPI application bound to the real OnboardAI workflow.

    Args:
        live: use the live LLM supervisor/workers (requires ``GROQ_API_KEY``).
            Defaults to ``False`` so tests and local demos run on the existing
            deterministic offline adapter with real RAG.
        persistent: persist LangGraph checkpoint state in SQLite. Defaults to
            ``True``, matching the capstone's production posture.
        service: optional pre-built service. Tests pass one bound to a temporary
            runtime directory so they never touch the real ``runtime/`` state.
    """

    if service is None:
        service = OnboardAIService.build(live=live, persistent=persistent)
    configure_service(service)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        service.close()

    app = FastAPI(
        title="OnboardAI API",
        description=(
            "REST backend for the OnboardAI human-supervised HR onboarding "
            "dashboard. Wraps the existing LangGraph Supervisor + Workers workflow."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    # Allow the bundled React dashboard (Vite dev server and production build)
    # to call this API from a browser. No existing endpoint or workflow logic
    # is changed; this only relaxes the same-origin policy for the dashboard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
