"""Pydantic contracts for the boundary, supervisor, workers, synthesis, and approval."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

WorkerName = Literal["training", "hr_documents", "it_provisioning"]
RouteDestination = Literal["training", "hr_documents", "it_provisioning"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OnboardingRequest(StrictModel):
    case_id: str = Field(min_length=3, max_length=80)
    employee_id: str = Field(min_length=3, max_length=40)
    employee_name: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    manager_email: EmailStr
    start_date: date | None = None
    resume_text: str = Field(min_length=30, max_length=20_000)
    request_text: str = Field(
        default="Complete the employee's post-hire onboarding.",
        min_length=5,
        max_length=2_000,
    )
    requested_actions: list[WorkerName] = Field(
        default_factory=lambda: ["training", "hr_documents", "it_provisioning"]
    )
    preferred_language: Literal["English", "Arabic"] = "English"
    training_format: Literal["online", "in_person", "hybrid"] = "online"

    @field_validator("employee_name")
    @classmethod
    def reject_placeholder_names(cls, value: str) -> str:
        if value.lower() in {"test", "name", "employee"}:
            raise ValueError("Use a realistic synthetic name")
        return value

    @model_validator(mode="after")
    def require_unique_actions(self) -> "OnboardingRequest":
        if not self.requested_actions:
            raise ValueError("At least one onboarding action must be requested")
        if len(set(self.requested_actions)) != len(self.requested_actions):
            raise ValueError("requested_actions must not contain duplicates")
        return self


class WorkerAssignment(StrictModel):
    worker: WorkerName
    objective: str = Field(min_length=8, max_length=500)


class SupervisorPlan(StrictModel):
    assignments: list[WorkerAssignment]
    rationale: str = Field(min_length=10, max_length=800)


class SupervisorDecision(StrictModel):
    destination: RouteDestination
    reason: str = Field(min_length=8, max_length=400)
    confidence: Literal["high", "low"]


class Citation(StrictModel):
    source: str
    category: Literal["policy", "role", "training"]
    excerpt: str = Field(max_length=500)


class WorkerResult(StrictModel):
    worker: WorkerName
    summary: str = Field(min_length=10)
    recommendations: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    structured_data: dict[str, object] = Field(default_factory=dict)


class SynthesisResult(StrictModel):
    summary: str = Field(min_length=20, max_length=1_500)
    completed_workers: list[WorkerName]
    key_risks: list[str] = Field(default_factory=list)
    source_count: int = Field(ge=0)


class ApprovalDecision(StrictModel):
    approved: bool
    reviewer: str = Field(min_length=2, max_length=120)
    comments: str = Field(default="", max_length=1_000)
    approved_actions: list[WorkerName] = Field(default_factory=list)


class OnboardingOutcome(StrictModel):
    status: Literal["completed", "rejected"]
    case_id: str
    employee_id: str
    supervisor_plan: SupervisorPlan
    worker_results: dict[str, WorkerResult]
    synthesis: SynthesisResult
    approval: ApprovalDecision | None = None
    final_actions: list[str] = Field(default_factory=list)
