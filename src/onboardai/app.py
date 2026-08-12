"""Composition root for live and offline modes."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from .agents import (
    OfflineStateSupervisor,
    StructuredOutputSupervisor,
    build_live_workers,
    build_offline_workers,
)
from .config import Settings
from .documents import DraftRenderer
from .rag import KnowledgeBase, make_embeddings
from .schemas import OnboardingRequest
from .storage import EmployeeMemory, OperationsDatabase
from .workflow import AppServices, build_onboarding_workflow


@dataclass
class OnboardAIApp:
    workflow: object
    services: AppServices
    knowledge: KnowledgeBase
    checkpoint_connection: sqlite3.Connection | None = None

    def close(self) -> None:
        if self.checkpoint_connection is not None:
            self.checkpoint_connection.close()


def _make_checkpointer(settings: Settings, persistent: bool):
    if not persistent:
        return InMemorySaver(), None

    from langgraph.checkpoint.sqlite import SqliteSaver

    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    return SqliteSaver(connection), connection


def build_app(
    *,
    live: bool,
    real_embeddings: bool = False,
    persistent: bool = True,
    simulate_it_failure: bool | None = None,
    settings: Settings | None = None,
) -> OnboardAIApp:
    settings = settings or Settings.from_env(require_live_key=live)
    os.environ.setdefault("HF_HOME", str(settings.runtime_dir / "huggingface"))
    embedding_backend = settings.embedding_backend if (live or real_embeddings) else "hash"
    embeddings = make_embeddings(
        embedding_backend,
        settings.embedding_model,
        cache_folder=settings.runtime_dir / "huggingface",
    )
    knowledge = KnowledgeBase.build(settings.data_dir / "knowledge", embeddings)

    if live:
        from langchain_groq import ChatGroq

        model = ChatGroq(model=settings.model_name, temperature=0)
        supervisor = StructuredOutputSupervisor(model)
        workers = build_live_workers(model, knowledge)
    else:
        supervisor = OfflineStateSupervisor()
        workers = build_offline_workers(knowledge)

    checkpointer, connection = _make_checkpointer(settings, persistent)
    services = AppServices(
        supervisor=supervisor,
        workers=workers,
        operations=OperationsDatabase(settings.operations_path),
        memory=EmployeeMemory(),
        renderer=DraftRenderer(settings.data_dir / "templates", settings.drafts_dir),
        simulate_it_failure=(
            settings.simulate_it_failure if simulate_it_failure is None else simulate_it_failure
        ),
    )
    workflow = build_onboarding_workflow(services, checkpointer)
    return OnboardAIApp(
        workflow=workflow,
        services=services,
        knowledge=knowledge,
        checkpoint_connection=connection,
    )


def load_sample_requests(path: Path | None = None) -> list[OnboardingRequest]:
    path = path or Settings().data_dir / "sample_requests.json"
    payloads = json.loads(path.read_text(encoding="utf-8"))
    return [OnboardingRequest.model_validate(payload) for payload in payloads]
