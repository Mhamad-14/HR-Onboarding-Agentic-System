"""LangGraph Functional API orchestration for the Track A capstone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.func import entrypoint, task
from langgraph.types import RetryPolicy, interrupt

from .agents import Supervisor, WorkerRegistry
from .documents import DraftRenderer
from .schemas import (
    ApprovalDecision,
    OnboardingOutcome,
    OnboardingRequest,
    SupervisorDecision,
    WorkerName,
    WorkerResult,
)
from .storage import EmployeeMemory, OperationsDatabase, TransientITError


@dataclass
class AppServices:
    supervisor: Supervisor
    workers: WorkerRegistry
    operations: OperationsDatabase
    memory: EmployeeMemory
    renderer: DraftRenderer
    simulate_it_failure: bool = False


def _requested_access(result: WorkerResult) -> list[str]:
    raw = result.structured_data.get("requested_access", result.recommendations)
    if not isinstance(raw, list):
        raise TypeError("IT worker structured_data.requested_access must be a list")
    return [str(value) for value in raw]


def build_onboarding_workflow(services: AppServices, checkpointer: Any):
    """Create the durable workflow; nested tasks keep injected services testable."""

    @task
    def validate_request(payload: dict) -> dict:
        return OnboardingRequest.model_validate(payload).model_dump(mode="json")

    @task
    def remember_safe_preferences(payload: dict) -> dict:
        request = OnboardingRequest.model_validate(payload)
        services.memory.remember_preferences(
            request.employee_id,
            preferred_language=request.preferred_language,
            training_format=request.training_format,
        )
        return services.memory.recall_preferences(request.employee_id) or {}

    @task
    def supervisor_route(
        payload: dict,
        completed: list[str],
        feedback: str,
    ) -> dict:
        request = OnboardingRequest.model_validate(payload)
        decision = services.supervisor.decide(request, set(completed), feedback)
        print(
            f"[supervisor] destination={decision.destination} "
            f"confidence={decision.confidence} reason={decision.reason}"
        )
        return decision.model_dump(mode="json")

    @task
    def run_training_worker(payload: dict) -> dict:
        request = OnboardingRequest.model_validate(payload)
        return services.workers.run("training", request).model_dump(mode="json")

    @task
    def run_hr_documents_worker(payload: dict) -> dict:
        request = OnboardingRequest.model_validate(payload)
        return services.workers.run("hr_documents", request).model_dump(mode="json")

    @task
    def run_it_planning_worker(payload: dict) -> dict:
        request = OnboardingRequest.model_validate(payload)
        return services.workers.run("it_provisioning", request).model_dump(mode="json")

    @task(
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_interval=0.1,
            retry_on=TransientITError,
        )
    )
    def create_draft_it_ticket(payload: dict, result_payload: dict) -> dict:
        request = OnboardingRequest.model_validate(payload)
        result = WorkerResult.model_validate(result_payload)
        return services.operations.create_draft_it_ticket(
            case_id=request.case_id,
            employee_id=request.employee_id,
            requested_access=_requested_access(result),
            risk_flags=result.risk_flags,
            fail_first_attempt=services.simulate_it_failure,
        )

    @task
    def render_reversible_drafts(payload: dict, results_payload: dict[str, dict]) -> list[str]:
        request = OnboardingRequest.model_validate(payload)
        results = {
            name: WorkerResult.model_validate(result) for name, result in results_payload.items()
        }
        return services.renderer.render_case_drafts(request, results)

    @task
    def finalize_approved_actions(
        payload: dict,
        results_payload: dict[str, dict],
        approval_payload: dict,
        draft_paths: list[str],
    ) -> list[str]:
        request = OnboardingRequest.model_validate(payload)
        approval = ApprovalDecision.model_validate(approval_payload)
        approved_actions = approval.approved_actions or request.requested_actions
        actions: list[str] = []

        if "it_provisioning" in approved_actions and "it_provisioning" in results_payload:
            actions.append(services.operations.approve_it_ticket(request.case_id))
        if "hr_documents" in approved_actions:
            actions.append("HR document drafts marked REVIEWED (not externally sent)")
        if "training" in approved_actions:
            training = WorkerResult.model_validate(results_payload["training"])
            services.memory.record_completed_training(request.employee_id, [])
            actions.append(
                "Training plan approved: " + ", ".join(training.recommendations or ["none"])
            )

        services.operations.record_event(
            request.case_id,
            "human_approval_completed",
            {
                "reviewer": approval.reviewer,
                "comments": approval.comments,
                "approved_actions": approved_actions,
                "draft_paths": draft_paths,
                "actions": actions,
            },
        )
        return actions

    @entrypoint(checkpointer=checkpointer, store=services.memory.store)
    def onboarding_workflow(payload: dict) -> dict:
        request_payload = validate_request(payload).result()
        request = OnboardingRequest.model_validate(request_payload)

        if request.start_date is None:
            supplied = interrupt(
                {
                    "type": "missing_information",
                    "case_id": request.case_id,
                    "field": "start_date",
                    "message": "A start date is required. Supply {'start_date': 'YYYY-MM-DD'}.",
                }
            )
            if not isinstance(supplied, dict) or "start_date" not in supplied:
                raise ValueError("Resume payload must contain start_date")
            updated_payload = request.model_dump(mode="json")
            updated_payload["start_date"] = supplied["start_date"]
            request_payload = updated_payload
            request_payload = validate_request(request_payload).result()
            request = OnboardingRequest.model_validate(request_payload)

        remembered_preferences = remember_safe_preferences(request_payload).result()
        results: dict[str, dict] = {}
        routing_log: list[dict] = []
        feedback = ""
        max_routing_steps = len(request.requested_actions) * 3 + 2

        for _ in range(max_routing_steps):
            decision_payload = supervisor_route(request_payload, sorted(results), feedback).result()
            decision = SupervisorDecision.model_validate(decision_payload)
            routing_log.append(decision_payload)

            if decision.destination == "complete":
                missing = set(request.requested_actions) - set(results)
                if missing:
                    feedback = (
                        "The previous decision tried to complete too early. "
                        f"Unfinished workers: {sorted(missing)}"
                    )
                    continue
                break

            if decision.destination == "human_review":
                feedback = (
                    "Human review is performed after all specialists finish. "
                    "Select an unfinished requested specialist now."
                )
                continue

            destination: WorkerName = decision.destination
            if destination not in request.requested_actions:
                feedback = (
                    f"{destination} was not requested. Select from {request.requested_actions}."
                )
                continue
            if destination in results:
                feedback = f"{destination} already completed. Select an unfinished worker."
                continue

            if destination == "training":
                result_payload = run_training_worker(request_payload).result()
            elif destination == "hr_documents":
                result_payload = run_hr_documents_worker(request_payload).result()
            else:
                result_payload = run_it_planning_worker(request_payload).result()
                ticket = create_draft_it_ticket(request_payload, result_payload).result()
                result = WorkerResult.model_validate(result_payload)
                result_payload = result.model_copy(
                    update={"artifacts": result.artifacts + [f"it-ticket:{ticket['ticket_id']}"]}
                ).model_dump(mode="json")
            results[destination] = result_payload
            feedback = ""
        else:
            raise RuntimeError("Supervisor failed to complete routing within the safety limit")

        draft_paths = render_reversible_drafts(request_payload, results).result()
        risk_flags = sorted(
            {
                flag
                for result in results.values()
                for flag in WorkerResult.model_validate(result).risk_flags
            }
        )
        approval_payload = interrupt(
            {
                "type": "human_approval",
                "case_id": request.case_id,
                "employee_id": request.employee_id,
                "message": "Review drafts and proposed actions before approval.",
                "proposed_actions": request.requested_actions,
                "risk_flags": risk_flags,
                "draft_paths": draft_paths,
                "remembered_preferences": remembered_preferences,
            }
        )
        approval = ApprovalDecision.model_validate(approval_payload)

        if not approval.approved:
            services.operations.record_event(
                request.case_id,
                "human_approval_rejected",
                {"reviewer": approval.reviewer, "comments": approval.comments},
            )
            return OnboardingOutcome(
                status="rejected",
                case_id=request.case_id,
                employee_id=request.employee_id,
                routing_log=[SupervisorDecision.model_validate(item) for item in routing_log],
                worker_results={
                    name: WorkerResult.model_validate(value) for name, value in results.items()
                },
                approval=approval,
                final_actions=[],
            ).model_dump(mode="json")

        final_actions = finalize_approved_actions(
            request_payload,
            results,
            approval.model_dump(mode="json"),
            draft_paths,
        ).result()
        return OnboardingOutcome(
            status="completed",
            case_id=request.case_id,
            employee_id=request.employee_id,
            routing_log=[SupervisorDecision.model_validate(item) for item in routing_log],
            worker_results={
                name: WorkerResult.model_validate(value) for name, value in results.items()
            },
            approval=approval,
            final_actions=final_actions,
        ).model_dump(mode="json")

    return onboarding_workflow
