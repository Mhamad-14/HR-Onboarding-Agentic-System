from langgraph.types import Command

from onboardai.app import build_app, load_sample_requests
from onboardai.schemas import ApprovalDecision


def _interrupt_value(result):
    interrupt_obj = result["__interrupt__"][0]
    return getattr(interrupt_obj, "value", interrupt_obj)


def test_full_workflow_retries_interrupts_and_resumes(test_settings):
    app = build_app(
        live=False,
        persistent=False,
        simulate_it_failure=True,
        settings=test_settings,
    )
    try:
        request = load_sample_requests()[0]
        config = {"configurable": {"thread_id": "full-workflow-test"}}

        paused = app.workflow.invoke(
            request.model_dump(mode="json"),
            config=config,
        )
        approval_payload = _interrupt_value(paused)

        assert approval_payload["type"] == "human_approval"
        assert app.services.operations.it_attempts[request.case_id] == 2

        approval = ApprovalDecision(
            approved=True,
            reviewer="Test Reviewer",
            comments="Approved in automated integration test.",
            approved_actions=request.requested_actions,
        )
        completed = app.workflow.invoke(
            Command(resume=approval.model_dump(mode="json")),
            config=config,
        )

        assert completed["status"] == "completed"
        assert set(completed["worker_results"]) == set(request.requested_actions)
        assert any("IT ticket" in action for action in completed["final_actions"])
        assert app.services.memory.recall_completed_training(request.employee_id)
    finally:
        app.close()


def test_missing_start_date_is_user_fixable(test_settings):
    app = build_app(live=False, persistent=False, settings=test_settings)
    try:
        request = load_sample_requests()[2]
        config = {"configurable": {"thread_id": "missing-date-test"}}

        paused = app.workflow.invoke(
            request.model_dump(mode="json"),
            config=config,
        )
        missing_payload = _interrupt_value(paused)
        assert missing_payload["type"] == "missing_information"
        assert missing_payload["field"] == "start_date"

        approval_pause = app.workflow.invoke(
            Command(resume={"start_date": "2026-09-20"}),
            config=config,
        )
        assert _interrupt_value(approval_pause)["type"] == "human_approval"
    finally:
        app.close()
