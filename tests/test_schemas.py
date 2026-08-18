import pytest
from pydantic import ValidationError

from onboardai.app import load_sample_requests
from onboardai.schemas import OnboardingRequest, SupervisorDecision


def test_sample_requests_are_valid_and_synthetic():
    requests = load_sample_requests()
    assert len(requests) == 3
    assert all("example.com" in request.manager_email for request in requests)


def test_boundary_rejects_unknown_fields():
    payload = load_sample_requests()[0].model_dump(mode="json")
    payload["protected_attribute"] = "must not be processed"
    with pytest.raises(ValidationError):
        OnboardingRequest.model_validate(payload)


def test_supervisor_destination_is_constrained():
    with pytest.raises(ValidationError):
        SupervisorDecision(
            destination="invented_worker",
            reason="This destination has no corresponding implementation.",
            confidence="high",
        )
