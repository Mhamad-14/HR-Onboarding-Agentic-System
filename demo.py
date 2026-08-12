"""Evidence-oriented CLI for the final capstone."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .app import build_app, load_sample_requests
from .config import langsmith_status
from .evaluation import run_retrieval_smoke_tests
from .schemas import ApprovalDecision
from .workflow import build_preference_memory_workflow


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _interrupt_payload(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__", ()) if isinstance(result, dict) else ()
    if not interrupts:
        return None
    first = interrupts[0]
    return getattr(first, "value", first)


def run_rag_evidence(*, live_embeddings: bool) -> None:
    app = build_app(live=False, real_embeddings=live_embeddings, persistent=False)
    try:
        report = app.knowledge.evidence_report(
            "Which approved training and access are required for a Software Engineer who lacks Docker?"
        )
        _print_json(report)
        smoke = run_retrieval_smoke_tests(app.knowledge)
        _print_json({"retrieval_smoke_tests": smoke})
        if not all(item["passed"] for item in smoke):
            raise RuntimeError("A retrieval smoke test failed")
    finally:
        app.close()


def run_routing_evidence() -> None:
    app = build_app(live=True, persistent=False)
    try:
        available = ["training", "hr_documents", "it_provisioning"]
        scenarios = [
            "Create only a cited 30/60/90-day learning plan for this employee.",
            "Prepare only the least-privilege workspace access request.",
            "Prepare only the HR onboarding notification and checklist drafts.",
        ]
        for request_text in scenarios:
            decision = app.services.supervisor.route_once(
                request_text=request_text,
                role="Software Engineer",
                department="Engineering",
                available_workers=available,
            )
            _print_json(
                {
                    "request": request_text,
                    "available_workers": available,
                    "llm_destination": decision.destination,
                    "reason": decision.reason,
                    "confidence": decision.confidence,
                }
            )
    finally:
        app.close()


def run_memory_evidence() -> None:
    app = build_app(live=False, persistent=False)
    try:
        memory_workflow = build_preference_memory_workflow(
            app.services.memory,
            checkpointer=InMemorySaver(),
        )

        cfg_a = {"configurable": {"thread_id": "thread-A"}}
        cfg_b = {"configurable": {"thread_id": "thread-B"}}

        a = memory_workflow.invoke(
            {
                "employee_id": "EMP-CROSS-THREAD",
                "preferred_language": "Arabic",
                "training_format": "online",
            },
            cfg_a,
        )
        b = memory_workflow.invoke(
            {"employee_id": "EMP-CROSS-THREAD"},
            cfg_b,
        )

        _print_json({"thread_id": "thread-A", "result": a})
        _print_json({"thread_id": "thread-B", "result": b})

        assert a["recalled_preferences"] == b["recalled_preferences"]
        print("CROSS-THREAD STORE PROOF: the preference survived a new thread_id.")
    finally:
        app.close()


def run_full(*, live: bool, case_index: int, simulate_failure: bool) -> None:
    app = build_app(
        live=live,
        persistent=True,
        simulate_it_failure=simulate_failure,
    )
    try:
        request = load_sample_requests()[case_index]
        thread_id = f"{request.case_id}-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        print(f"MODE: {'LIVE LLM' if live else 'OFFLINE TEST ADAPTER'}")
        print(f"THREAD_ID: {thread_id}")

        result = app.workflow.invoke(request.model_dump(mode="json"), config=config)
        payload = _interrupt_payload(result)

        if payload and payload.get("type") == "missing_information":
            print("\nPAUSED FOR REQUIRED INFORMATION")
            _print_json(payload)
            result = app.workflow.invoke(
                Command(resume={"start_date": "2026-09-20"}),
                config=config,
            )
            payload = _interrupt_payload(result)

        if not payload or payload.get("type") != "human_approval":
            raise RuntimeError(f"Expected human_approval interrupt, received: {result}")

        print("\nPAUSED FOR HUMAN APPROVAL")
        _print_json(payload)

        approval = ApprovalDecision(
            approved=True,
            reviewer="Capstone HR Reviewer",
            comments="Reviewed and approved for the synthetic capstone demonstration.",
            approved_actions=request.requested_actions,
        )
        final = app.workflow.invoke(
            Command(resume=approval.model_dump(mode="json")),
            config=config,
        )
        print("\nRESUMED AND COMPLETED")
        _print_json(final)
        print("\nAUDIT EVENTS")
        _print_json(app.services.operations.list_events(request.case_id))
    finally:
        app.close()


def run_langsmith_check() -> None:
    status = langsmith_status()
    _print_json(status)

    if not status["api_key_present"]:
        raise RuntimeError("LANGSMITH_API_KEY is missing")
    if not status["course_tracing_flag"]:
        raise RuntimeError("LANGCHAIN_TRACING_V2 must be set to 'true'")

    from langsmith import Client

    client = Client()
    list(client.list_projects(limit=1))
    print("LangSmith key is valid and reachable. No secret value was printed.")


def inspect_langsmith_runs(limit: int = 30) -> None:
    from langsmith import Client

    status = langsmith_status()
    project = str(status["project"])
    client = Client()

    time.sleep(2)
    runs = list(client.list_runs(project_name=project, limit=limit))
    if not runs:
        raise RuntimeError(
            "No LangSmith runs were returned. Execute a live workflow first and verify tracing."
        )

    def latency_seconds(run):
        if getattr(run, "start_time", None) and getattr(run, "end_time", None):
            return (run.end_time - run.start_time).total_seconds()
        return None

    measured = [
        (run.name, latency_seconds(run), bool(getattr(run, "error", None)))
        for run in runs
        if latency_seconds(run) is not None
    ]

    print("LANGSMITH PROJECT:", project)
    print("RECENT RUNS INSPECTED:", len(runs))
    print("RUNS WITH ERROR FLAG:", sum(1 for run in runs if getattr(run, "error", None)))

    if measured:
        slowest = max(measured, key=lambda row: row[1])
        print(
            "TRACE-BASED OBSERVATION:",
            f"The slowest inspected run was {slowest[0]!r} at about {slowest[1]:.3f}s.",
        )

    error_names = [
        run.name for run in runs if getattr(run, "error", None)
    ]
    if error_names:
        print("TRACE-BASED OBSERVATION: traced error/retry-related runs:", error_names[:8])
    else:
        print("TRACE-BASED OBSERVATION: no final error flag appeared in these inspected runs.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rag = sub.add_parser("rag-evidence")
    rag.add_argument("--live-embeddings", action="store_true")

    sub.add_parser("live-routing")
    sub.add_parser("memory-evidence")
    sub.add_parser("langsmith-check")
    sub.add_parser("inspect-langsmith")

    for name in ("offline-full", "live-full"):
        command = sub.add_parser(name)
        command.add_argument("--case-index", type=int, choices=range(3), default=0)
        command.add_argument("--simulate-it-failure", action="store_true")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "rag-evidence":
        run_rag_evidence(live_embeddings=args.live_embeddings)
    elif args.command == "live-routing":
        run_routing_evidence()
    elif args.command == "memory-evidence":
        run_memory_evidence()
    elif args.command == "langsmith-check":
        run_langsmith_check()
    elif args.command == "inspect-langsmith":
        inspect_langsmith_runs()
    elif args.command == "offline-full":
        run_full(
            live=False,
            case_index=args.case_index,
            simulate_failure=args.simulate_it_failure,
        )
    else:
        run_full(
            live=True,
            case_index=args.case_index,
            simulate_failure=args.simulate_it_failure,
        )


if __name__ == "__main__":
    main()
