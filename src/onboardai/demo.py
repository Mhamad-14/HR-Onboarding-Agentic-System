"""Evidence-oriented CLI. Live commands require GROQ_API_KEY."""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from langgraph.types import Command

from .app import build_app, load_sample_requests
from .config import langsmith_status
from .evaluation import run_retrieval_smoke_tests
from .schemas import ApprovalDecision


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _interrupt_payload(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__", ()) if isinstance(result, dict) else ()
    if not interrupts:
        return None
    first = interrupts[0]
    return getattr(first, "value", first)


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
        print(f"THREAD: {thread_id}")
        result = app.workflow.invoke(request.model_dump(mode="json"), config=config)

        payload = _interrupt_payload(result)
        if payload and payload.get("type") == "missing_information":
            print("\nPAUSED FOR REQUIRED INFORMATION")
            _print_json(payload)
            result = app.workflow.invoke(
                Command(resume={"start_date": "2026-09-20"}), config=config
            )
            payload = _interrupt_payload(result)

        if not payload or payload.get("type") != "human_approval":
            raise RuntimeError(f"Expected human_approval interrupt, received: {result}")

        print("\nPAUSED FOR HUMAN APPROVAL")
        _print_json(payload)
        approval = ApprovalDecision(
            approved=True,
            reviewer="Synthetic HR Reviewer",
            comments="Approved for the capstone demonstration.",
            approved_actions=request.requested_actions,
        )
        final = app.workflow.invoke(Command(resume=approval.model_dump(mode="json")), config=config)
        print("\nRESUMED AND COMPLETED")
        _print_json(final)
        print("\nAUDIT EVENTS")
        _print_json(app.services.operations.list_events(request.case_id))
    finally:
        app.close()


def run_routing_evidence() -> None:
    app = build_app(live=True, persistent=False)
    try:
        samples = load_sample_requests()
        training_only = samples[0].model_copy(
            update={
                "request_text": "Create a cited 30/60/90-day training plan for this employee.",
                "requested_actions": ["training"],
            }
        )
        it_only = samples[1].model_copy(
            update={
                "request_text": "Prepare the least-privilege workspace access request.",
                "requested_actions": ["it_provisioning"],
            }
        )
        for request in (training_only, it_only):
            decision = app.services.supervisor.decide(request, set())
            _print_json(
                {
                    "request": request.request_text,
                    "destination": decision.destination,
                    "reason": decision.reason,
                    "confidence": decision.confidence,
                }
            )
    finally:
        app.close()


def run_rag_evidence(*, live_embeddings: bool) -> None:
    app = build_app(
        live=False,
        real_embeddings=live_embeddings,
        persistent=False,
    )
    try:
        report = app.knowledge.evidence_report(
            "Which training and access are required for a Software Engineer who lacks Docker?"
        )
        report["embedding_mode"] = "huggingface" if live_embeddings else "offline hash test double"
        _print_json(report)
    finally:
        app.close()


def run_memory_evidence() -> None:
    app = build_app(live=False, persistent=False)
    try:
        employee_id = "EMP-CROSS-THREAD"
        thread_a = "thread-A"
        thread_b = "thread-B"
        app.services.memory.remember_preferences(
            employee_id,
            preferred_language="Arabic",
            training_format="online",
        )
        _print_json(
            {
                "thread_A": thread_a,
                "written_fact": app.services.memory.recall_preferences(employee_id),
            }
        )
        _print_json(
            {
                "thread_B": thread_b,
                "same_employee": employee_id,
                "recalled_from_separate_Store": app.services.memory.recall_preferences(employee_id),
                "conversation_history_inherited": False,
            }
        )
    finally:
        app.close()


def run_evaluation() -> None:
    app = build_app(live=False, persistent=False)
    try:
        results = run_retrieval_smoke_tests(app.knowledge)
        _print_json(results)
        if not all(result["passed"] for result in results):
            raise RuntimeError("One or more retrieval smoke tests failed")
    finally:
        app.close()


def run_langsmith_check() -> None:
    status = langsmith_status()
    _print_json(status)
    if not status["api_key_present"]:
        raise RuntimeError("LANGSMITH_API_KEY is missing")
    from langsmith import Client

    client = Client()
    list(client.list_projects(limit=1))
    print("LangSmith key is valid and reachable. No secret value was printed.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("offline-full", "live-full"):
        command = subparsers.add_parser(name)
        command.add_argument("--case-index", type=int, choices=range(3), default=0)
        command.add_argument("--simulate-it-failure", action="store_true")

    subparsers.add_parser("live-routing")
    rag = subparsers.add_parser("rag-evidence")
    rag.add_argument("--live-embeddings", action="store_true")
    subparsers.add_parser("memory-evidence")
    subparsers.add_parser("evaluate-rag")
    subparsers.add_parser("langsmith-check")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "offline-full":
        run_full(
            live=False,
            case_index=args.case_index,
            simulate_failure=args.simulate_it_failure,
        )
    elif args.command == "live-full":
        run_full(
            live=True,
            case_index=args.case_index,
            simulate_failure=args.simulate_it_failure,
        )
    elif args.command == "live-routing":
        run_routing_evidence()
    elif args.command == "rag-evidence":
        run_rag_evidence(live_embeddings=args.live_embeddings)
    elif args.command == "memory-evidence":
        run_memory_evidence()
    elif args.command == "evaluate-rag":
        run_evaluation()
    else:
        run_langsmith_check()


if __name__ == "__main__":
    main()
