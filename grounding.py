"""Deterministic grounding checks that prevent model-invented HR course IDs or access names."""

from __future__ import annotations

import csv
from pathlib import Path

from .schemas import OnboardingRequest, WorkerResult


def _split_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _training_rows(knowledge_dir: Path) -> list[dict[str, str]]:
    with (knowledge_dir / "training_catalog.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _role_rows(knowledge_dir: Path) -> list[dict[str, str]]:
    with (knowledge_dir / "role_competencies.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def approved_courses_for_role(knowledge_dir: Path, role: str) -> list[str]:
    rows = _training_rows(knowledge_dir)
    return [
        row["course_id"]
        for row in rows
        if row["mandatory_for"].strip().lower() in {"all employees", role.lower()}
    ]


def approved_access_for_role(knowledge_dir: Path, role: str) -> tuple[list[str], list[str]]:
    for row in _role_rows(knowledge_dir):
        if row["role"].strip().lower() == role.lower():
            return _split_values(row["standard_access"]), _split_values(row["privileged_access"])
    raise LookupError(f"No approved role-to-access row exists for role={role!r}")


def ground_worker_result(
    request: OnboardingRequest,
    result: WorkerResult,
    knowledge_dir: Path,
) -> WorkerResult:
    """Replace unsupported action identifiers with values from the approved source files."""

    if result.worker == "training":
        approved = approved_courses_for_role(knowledge_dir, request.role)
        all_ids = {row["course_id"] for row in _training_rows(knowledge_dir)}
        model_valid = [item for item in result.recommendations if item in all_ids]
        removed = [item for item in result.recommendations if item not in all_ids]

        final_ids: list[str] = []
        for course_id in approved + model_valid:
            if course_id not in final_ids:
                final_ids.append(course_id)

        general = [
            course_id
            for course_id in final_ids
            if course_id in {"SEC-101", "COL-100"}
        ]
        role_specific = [course_id for course_id in final_ids if course_id not in general]
        day_30 = general + role_specific[:1]
        day_60 = role_specific[1:2]
        day_90 = role_specific[2:]

        # Final human-review risks must be grounded in approved source data.
        # Invalid model course IDs are corrected internally rather than surfaced as HR risks.
        risk_flags: list[str] = []

        structured = dict(result.structured_data)
        structured.update(
            {
                "day_30": day_30,
                "day_60": day_60,
                "day_90": day_90,
                "grounded_course_ids": final_ids,
            }
        )
        return result.model_copy(
            update={
                "recommendations": final_ids,
                "risk_flags": risk_flags,
                "structured_data": structured,
                "summary": result.summary
                + " Course identifiers were validated against training_catalog.csv.",
            }
        )

    if result.worker == "it_provisioning":
        standard, privileged = approved_access_for_role(knowledge_dir, request.role)
        requested_access = standard + privileged
        structured = dict(result.structured_data)
        structured.update(
            {
                "standard_access": standard,
                "privileged_access": privileged,
                "requested_access": requested_access,
                "status": "DRAFT",
            }
        )
        risk_flags = [
            f"Privileged access requires additional human approval: {item}"
            for item in privileged
        ]
        return result.model_copy(
            update={
                "recommendations": requested_access,
                "risk_flags": risk_flags,
                "structured_data": structured,
                "summary": result.summary
                + " Access names were validated against role_competencies.csv.",
            }
        )

    # HR document recommendations are kept reversible and policy-scoped.
    # Required request fields have already been validated before workers run, so speculative
    # model risks such as "Missing manager information" must not survive grounding.
    structured = dict(result.structured_data)
    structured["status"] = "DRAFT_ONLY"
    return result.model_copy(
        update={
            "recommendations": [
                "Prepare manager welcome notification draft",
                "Prepare onboarding checklist",
                "Prepare contract notification draft",
                "Require authorized HR review before any external send",
            ],
            "risk_flags": [],
            "structured_data": structured,
        }
    )
