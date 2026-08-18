"""LangGraph Functional API workflow for Track A + Orchestrator-Worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import RetryPolicy, interrupt

from .agents import Supervisor, WorkerRegistry
from .documents import DraftRenderer
from .schemas import (
    ApprovalDecision,
    OnboardingOutcome,
    OnboardingRequest,
    SupervisorPlan,
    SynthesisResult,
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


def build_preference_memory_workflow(
    memory: EmployeeMemory,
    *,
    checkpointer: Any | None = None,
):
    """Tiny workflow used only to prove Store memory across different thread IDs."""

    checkpointer = checkpointer or InMemorySaver()

    @entrypoint(checkpointer=checkpointer, store=memory.store)
    def preference_workflow(inputs: dict) -> dict:
        employee_id = str(inputs["employee_id"])

        if "preferred_language" in inputs or "training_format" in inputs:
            previous = memory.recall_preferences(employee_id) or {}
            memory.remember_preferences(
                employee_id,
                preferred_language=str(
                    inputs.get("preferred_language", previous.get("preferred_language", "English"))
                ),
                training_format=str(
                    inputs.get("training_format", previous.get("training_format", "online"))
                ),
            )

        return {
            "employee_id": employee_id,
            "recalled_preferences": memory.recall_preferences(employee_id),
        }

    return preference_workflow


def build_onboarding_workflow(services: AppServices, checkpointer: Any):
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
    def plan_work(payload: dict) -> dict:
        request = OnboardingRequest.model_validate(payload)
        plan = services.supervisor.plan(request)
        print("[ORCHESTRATOR] rationale:", plan.rationale)
        for assignment in plan.assignments:
            print(
                "[LLM SUPERVISOR ASSIGNMENT] "
                f"worker={assignment.worker} objective={assignment.objective}"
            )
        return plan.model_dump(mode="json")

    @task
    def run_training_worker(payload: dict, objective: str) -> dict:
        request = OnboardingRequest.model_validate(payload)
        print("[WORKER START] training |", objective)
        return services.workers.run("training", request).model_dump(mode="json")

    @task
    def run_hr_documents_worker(payload: dict, objective: str) -> dict:
        request = OnboardingRequest.model_validate(payload)
        print("[WORKER START] hr_documents |", objective)
        return services.workers.run("hr_documents", request).model_dump(mode="json")

    @task
    def run_it_planning_worker(payload: dict, objective: str) -> dict:
        request = OnboardingRequest.model_validate(payload)
        print("[WORKER START] it_provisioning |", objective)
        return services.workers.run("it_provisioning", request).model_dump(mode="json")

    @task(
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_interval=0.2,
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
    def synthesize_worker_outputs(payload: dict, results_payload: dict[str, dict]) -> dict:
        request = OnboardingRequest.model_validate(payload)
        results = {
            name: WorkerResult.model_validate(value)
            for name, value in results_payload.items()
        }
        synthesis = services.supervisor.synthesize(request, results)
        print("[SYNTHESIZER]", synthesis.summary)
        return synthesis.model_dump(mode="json")

    @task
    def render_reversible_drafts(payload: dict, results_payload: dict[str, dict]) -> list[str]:
        request = OnboardingRequest.model_validate(payload)
        results = {
            name: WorkerResult.model_validate(value)
            for name, value in results_payload.items()
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

        if "training" in approved_actions and "training" in results_payload:
            training = WorkerResult.model_validate(results_payload["training"])
            services.memory.record_completed_training(
                request.employee_id,
                training.recommendations,
            )
            actions.append(
                "Training plan approved: "
                + ", ".join(training.recommendations or ["none"])
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

        # Reliability strategy: user-fixable missing information.
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

            updated = request.model_dump(mode="json")
            updated["start_date"] = supplied["start_date"]
            request_payload = validate_request(updated).result()
            request = OnboardingRequest.model_validate(request_payload)

        remembered_preferences = remember_safe_preferences(request_payload).result()

        # Orchestrator phase: LLM creates a dynamic plan.
        plan_payload = plan_work(request_payload).result()
        plan = SupervisorPlan.model_validate(plan_payload)

        # Worker phase: execute the supervisor-selected independent specialists.
        # Sequential execution is deliberate here: it is more reliable on free-tier API limits,
        # while the assignments themselves are still dynamically created by the orchestrator.
        results: dict[str, dict] = {}
        for assignment in plan.assignments:
            if assignment.worker == "training":
                results["training"] = run_training_worker(
                    request_payload, assignment.objective
                ).result()
            elif assignment.worker == "hr_documents":
                results["hr_documents"] = run_hr_documents_worker(
                    request_payload, assignment.objective
                ).result()
            else:
                results["it_provisioning"] = run_it_planning_worker(
                    request_payload, assignment.objective
                ).result()

        if "it_provisioning" in results:
            ticket = create_draft_it_ticket(
                request_payload,
                results["it_provisioning"],
            ).result()
            it_result = WorkerResult.model_validate(results["it_provisioning"])
            results["it_provisioning"] = it_result.model_copy(
                update={
                    "artifacts": it_result.artifacts
                    + [f"it-ticket:{ticket['ticket_id']}"]
                }
            ).model_dump(mode="json")

        # Synthesizer phase required by the Orchestrator-Worker pattern.
        synthesis_payload = synthesize_worker_outputs(
            request_payload,
            results,
        ).result()
        synthesis = SynthesisResult.model_validate(synthesis_payload)

        draft_paths = render_reversible_drafts(request_payload, results).result()
        risk_flags = sorted(
            {
                flag
                for result in results.values()
                for flag in WorkerResult.model_validate(result).risk_flags
            }
        )

        # Human-in-the-loop: pause immediately before consequential finalization.
        approval_payload = interrupt(
            {
                "type": "human_approval",
                "case_id": request.case_id,
                "employee_id": request.employee_id,
                "message": "Review drafts and proposed actions before approval.",
                  "worker_results": {
                       name: WorkerResult.model_validate(value).model_dump(mode="json")
                       for name, value in results.items()
                },
                "proposed_actions": request.requested_actions,
                "risk_flags": risk_flags,
                "synthesis": synthesis.model_dump(mode="json"),
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
                supervisor_plan=plan,
                worker_results={
                    name: WorkerResult.model_validate(value)
                    for name, value in results.items()
                },
                synthesis=synthesis,
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
            supervisor_plan=plan,
            worker_results={
                name: WorkerResult.model_validate(value)
                for name, value in results.items()
            },
            synthesis=synthesis,
            approval=approval,
            final_actions=final_actions,
        ).model_dump(mode="json")

    return onboarding_workflow
