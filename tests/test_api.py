"""API tests for the FastAPI backend bound to the real OnboardAI workflow.

These tests run the actual LangGraph workflow in offline mode (the existing
deterministic supervisor + real RAG + grounding), so they verify the HTTP layer
against the real pipeline rather than mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from onboardai.api.main import create_app
from onboardai.api.service import OnboardAIService
from onboardai.app import load_sample_requests
from onboardai.config import Settings


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """One app per module: the workflow is stateful per thread_id, and each test
    uses its own thread_id so cases do not collide."""

    project_root = Path(__file__).resolve().parents[1]
    tmp_path = tmp_path_factory.mktemp("api-runtime")
    settings = Settings(
        project_root=project_root,
        data_dir=project_root / "data",
        runtime_dir=tmp_path,
        checkpoint_path=tmp_path / "checkpoints.db",
        operations_path=tmp_path / "operations.db",
        drafts_dir=tmp_path / "drafts",
        embedding_backend="hash",
        embedding_model="hash-test-double",
        simulate_it_failure=True,
    )

    service = OnboardAIService.build(
        live=False,
        persistent=False,
        settings=settings,
    )
    app = create_app(live=False, persistent=False, service=service)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        service.close()


def _request_payload(case_index: int = 0) -> dict:
    return load_sample_requests()[case_index].model_dump(mode="json")


def _submit(client: TestClient, thread_id: str, case_index: int = 0) -> dict:
    response = client.post(
        "/api/cases",
        json={"request": _request_payload(case_index), "thread_id": thread_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_reports_real_knowledge_base(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] == "offline"
    assert body["knowledge_documents"] >= 4
    assert body["knowledge_chunks"] > 0
    assert body["vector_store"] == "InMemoryVectorStore"


def test_submit_pauses_for_human_approval_and_returns_routing_and_workers(client):
    thread_id = "api-approval-001"
    body = _submit(client, thread_id)

    assert body["thread_id"] == thread_id
    assert body["outcome"] is None
    interrupt = body["interrupt"]
    assert interrupt is not None
    assert interrupt["type"] == "human_approval"
    value = interrupt["value"]
    assert value["case_id"] == "CASE-ENG-001"

    # Synthesis + risk flags produced by the real Orchestrator-Worker pipeline.
    assert "summary" in value["synthesis"]
    assert value["synthesis"]["completed_workers"] == [
        "training",
        "hr_documents",
        "it_provisioning",
    ]
    assert value["risk_flags"] == [
        "Privileged access requires additional human approval: VPN"
    ]
    assert len(value["draft_paths"]) == 2


def test_approval_resume_completes_case_with_citations_and_final_actions(client):
    thread_id = "api-approve-002"
    body = _submit(client, thread_id)
    assert body["interrupt"]["type"] == "human_approval"

    approval = {
        "approved": True,
        "reviewer": "API Test Reviewer",
        "comments": "Approved through the API.",
        "approved_actions": ["training", "hr_documents", "it_provisioning"],
    }
    resumed = client.post(
        f"/api/cases/{thread_id}/resume",
        json={"value": approval},
    )
    assert resumed.status_code == 200, resumed.text
    result = resumed.json()

    assert result["interrupt"] is None
    outcome = result["outcome"]
    assert outcome["status"] == "completed"
    assert set(outcome["worker_results"]) == {
        "training",
        "hr_documents",
        "it_provisioning",
    }

    # RAG citations survive from the real workers.
    for worker_result in outcome["worker_results"].values():
        assert worker_result["citations"], worker_result["worker"]
        assert all(citation["source"] for citation in worker_result["citations"])

    assert any("IT ticket" in action for action in outcome["final_actions"])
    assert outcome["approval"]["approved"] is True


def test_reject_resume_records_rejection_without_final_actions(client):
    thread_id = "api-reject-003"
    body = _submit(client, thread_id)
    assert body["interrupt"]["type"] == "human_approval"

    rejection = {
        "approved": False,
        "reviewer": "API Test Reviewer",
        "comments": "Rejected in test.",
    }
    resumed = client.post(
        f"/api/cases/{thread_id}/resume",
        json={"value": rejection},
    )
    assert resumed.status_code == 200, resumed.text
    result = resumed.json()

    assert result["outcome"]["status"] == "rejected"
    assert result["outcome"]["final_actions"] == []
    assert result["outcome"]["approval"]["approved"] is False


def test_missing_start_date_pauses_then_resumes_to_approval(client):
    thread_id = "api-missing-date-004"
    body = _submit(client, thread_id, case_index=2)
    assert body["interrupt"]["type"] == "missing_information"
    assert body["interrupt"]["value"]["field"] == "start_date"

    resumed = client.post(
        f"/api/cases/{thread_id}/resume",
        json={"value": {"start_date": "2026-09-20"}},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["interrupt"]["type"] == "human_approval"


def test_audit_events_are_recorded_after_approval(client):
    thread_id = "api-events-005"
    _submit(client, thread_id)
    approval = {
        "approved": True,
        "reviewer": "API Test Reviewer",
        "comments": "Approved for audit test.",
        "approved_actions": ["training", "hr_documents", "it_provisioning"],
    }
    client.post(f"/api/cases/{thread_id}/resume", json={"value": approval})

    response = client.get(f"/api/cases/{thread_id}/events")
    assert response.status_code == 200
    events = response.json()
    assert any(event["event_type"] == "human_approval_completed" for event in events)


def test_draft_files_are_listed_and_readable(client):
    thread_id = "api-drafts-006"
    _submit(client, thread_id)

    response = client.get(f"/api/cases/{thread_id}/drafts")
    assert response.status_code == 200
    drafts = response.json()
    assert len(drafts) == 2
    assert any(draft.endswith("_onboarding_proposal.md") for draft in drafts)

    content_response = client.get(f"/api/drafts/{drafts[0]}")
    assert content_response.status_code == 200
    content = content_response.json()
    assert "Draft onboarding notification" in content

    proposal = next(draft for draft in drafts if draft.endswith("_onboarding_proposal.md"))
    proposal_response = client.get(f"/api/drafts/{proposal}")
    assert proposal_response.status_code == 200
    assert "DRAFT" in proposal_response.json()


def test_unknown_draft_returns_404(client):
    response = client.get("/api/drafts/does-not-exist.md")
    assert response.status_code == 404


def test_knowledge_search_returns_cited_evidence(client):
    response = client.post(
        "/api/knowledge/search",
        json={"query": "Software Engineer Docker course and GitHub access", "k": 8},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["citations"]
    combined = " ".join(citation["excerpt"] for citation in body["citations"])
    assert "ENG-201" in combined
    assert "GitHub" in combined


def test_supervisor_route_returns_real_decision(client):
    response = client.post(
        "/api/supervisor/route",
        params={
            "request_text": "Create only a cited 30/60/90-day learning plan for this employee.",
            "role": "Software Engineer",
            "department": "Engineering",
            "available_workers": ["training", "hr_documents", "it_provisioning"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["destination"] in {"training", "hr_documents", "it_provisioning"}
    assert body["reason"]


def test_submit_rejects_invalid_request_payload(client):
    payload = _request_payload()
    payload["protected_attribute"] = "must not be processed"
    response = client.post(
        "/api/cases",
        json={"request": payload, "thread_id": "api-invalid-007"},
    )
    assert response.status_code == 422
