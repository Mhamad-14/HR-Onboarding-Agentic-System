from onboardai.app import load_sample_requests
from onboardai.grounding import ground_worker_result
from onboardai.schemas import WorkerResult


def test_training_grounding_removes_invented_course(project_root):
    request = load_sample_requests()[0]
    result = WorkerResult(
        worker="training",
        summary="Synthetic model result containing one invalid course identifier.",
        recommendations=["DOCKER-101", "ENG-201"],
    )
    grounded = ground_worker_result(
        request,
        result,
        project_root / "data" / "knowledge",
    )
    assert "DOCKER-101" not in grounded.recommendations
    assert "ENG-201" in grounded.recommendations
    assert "SEC-101" in grounded.recommendations
    assert "COL-100" in grounded.recommendations


def test_it_grounding_uses_exact_role_matrix(project_root):
    request = load_sample_requests()[0]
    result = WorkerResult(
        worker="it_provisioning",
        summary="Synthetic model output to be grounded.",
        recommendations=["administrator"],
    )
    grounded = ground_worker_result(
        request,
        result,
        project_root / "data" / "knowledge",
    )
    assert grounded.structured_data["standard_access"] == [
        "email",
        "identity",
        "GitHub",
        "issue tracker",
    ]
    assert grounded.structured_data["privileged_access"] == ["VPN"]


def test_training_grounding_drops_speculative_model_risks(project_root):
    request = load_sample_requests()[0]
    result = WorkerResult(
        worker="training",
        summary="Synthetic training result.",
        recommendations=["ENG-201"],
        risk_flags=[
            "Missing manager information",
            "Insufficient access controls",
        ],
    )
    grounded = ground_worker_result(
        request,
        result,
        project_root / "data" / "knowledge",
    )
    assert grounded.risk_flags == []


def test_hr_document_grounding_drops_false_missing_manager_risk(project_root):
    request = load_sample_requests()[0]
    assert request.manager_email
    assert request.start_date is not None

    result = WorkerResult(
        worker="hr_documents",
        summary="Synthetic HR document result.",
        risk_flags=[
            "Missing manager information",
            "Insufficient access controls",
        ],
    )
    grounded = ground_worker_result(
        request,
        result,
        project_root / "data" / "knowledge",
    )
    assert grounded.risk_flags == []


def test_software_engineer_final_it_risk_is_only_privileged_vpn(project_root):
    request = load_sample_requests()[0]
    result = WorkerResult(
        worker="it_provisioning",
        summary="Synthetic IT result.",
        risk_flags=[
            "Missing manager information",
            "Insufficient access controls",
        ],
    )
    grounded = ground_worker_result(
        request,
        result,
        project_root / "data" / "knowledge",
    )
    assert grounded.risk_flags == [
        "Privileged access requires additional human approval: VPN"
    ]
