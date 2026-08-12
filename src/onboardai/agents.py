"""Track A supervisor and specialist worker implementations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from .rag import KnowledgeBase, citations_as_context
from .schemas import (
    OnboardingRequest,
    SupervisorDecision,
    WorkerName,
    WorkerResult,
)


class Supervisor(Protocol):
    def decide(
        self,
        request: OnboardingRequest,
        completed: set[str],
        routing_feedback: str = "",
    ) -> SupervisorDecision: ...


class Worker(Protocol):
    name: WorkerName

    def run(self, request: OnboardingRequest) -> WorkerResult: ...


SUPERVISOR_PROMPT = """
You are the onboarding supervisor in a Track A Supervisor + Workers system.
Select exactly one unfinished requested specialist. Do not perform specialist work yourself.

Available workers:
- training: skill-gap analysis and cited training recommendations
- hr_documents: policy review and draft onboarding communications
- it_provisioning: role-based access planning and risk flags

Rules:
1. Never route based on protected characteristics.
2. Never choose a worker that is not requested.
3. Never choose an already completed worker.
4. Use complete only when all requested workers are complete.
5. Use low confidence if information is ambiguous; do not invent facts.
""".strip()


class StructuredOutputSupervisor:
    """The rubric-eligible supervisor: an LLM constrained by a Pydantic contract."""

    def __init__(self, model: BaseChatModel):
        self.router = model.with_structured_output(SupervisorDecision)

    def decide(
        self,
        request: OnboardingRequest,
        completed: set[str],
        routing_feedback: str = "",
    ) -> SupervisorDecision:
        prompt = (
            f"{SUPERVISOR_PROMPT}\n\n"
            f"User request: {request.request_text}\n"
            f"Role: {request.role}\nDepartment: {request.department}\n"
            f"Requested workers: {request.requested_actions}\n"
            f"Completed workers: {sorted(completed)}\n"
            f"Correction feedback: {routing_feedback or 'none'}"
        )
        return self.router.invoke(prompt)


class OfflineStateSupervisor:
    """Deterministic test double; never use its output as LLM-routing evidence."""

    def decide(
        self,
        request: OnboardingRequest,
        completed: set[str],
        routing_feedback: str = "",
    ) -> SupervisorDecision:
        for worker in request.requested_actions:
            if worker not in completed:
                return SupervisorDecision(
                    destination=worker,
                    reason=f"Offline test adapter selected unfinished requested worker: {worker}.",
                    confidence="high",
                )
        return SupervisorDecision(
            destination="complete",
            reason="All requested workers completed in the offline integration test.",
            confidence="high",
        )


def _build_retrieval_tool(knowledge: KnowledgeBase):
    @tool
    def search_approved_onboarding_knowledge(
        query: str,
        categories: list[str],
    ) -> str:
        """Search approved HR policies, role matrices, and training data with citations."""

        citations = knowledge.search(query, categories=categories, k=5)
        return json.dumps(
            {
                "citations": [citation.model_dump(mode="json") for citation in citations],
                "context": citations_as_context(citations),
            },
            ensure_ascii=False,
        )

    return search_approved_onboarding_knowledge


WORKER_PROMPTS: dict[WorkerName, str] = {
    "training": """
You are the Training Plan specialist. You MUST call the approved-knowledge search tool before
answering. Search the role matrix and training catalogue. Compare only job-relevant resume skills
with approved requirements. Return course IDs in recommendations, cite every material claim, and
put a 30/60/90-day plan in structured_data. Mandatory courses come from policy/catalogue data;
never infer protected traits and never invent a course.
""".strip(),
    "hr_documents": """
You are the HR Documents specialist. You MUST call the approved-knowledge search tool before
answering. Retrieve onboarding and data-minimization policy. Recommend draft documents and review
steps; do not claim that a document was sent or legally approved. Cite the policy evidence and put
the checklist in structured_data.
""".strip(),
    "it_provisioning": """
You are the IT Provisioning specialist. You MUST call the approved-knowledge search tool before
answering. Retrieve the exact role-to-access row and the security policy. Put exact access names
in structured_data.requested_access. Flag privileged access in risk_flags. You may recommend a
draft ticket, but you must not activate an account or approve access.
""".strip(),
}


class LiveSpecialistWorker:
    def __init__(self, name: WorkerName, model: BaseChatModel, knowledge: KnowledgeBase):
        self.name = name
        self.knowledge = knowledge
        retrieval_tool = _build_retrieval_tool(knowledge)
        self.agent = create_agent(
            model=model,
            tools=[retrieval_tool],
            system_prompt=WORKER_PROMPTS[name],
            response_format=ToolStrategy(WorkerResult),
        )

    def run(self, request: OnboardingRequest) -> WorkerResult:
        # Hybrid RAG: mandatory role/policy evidence is injected deterministically, while
        # the agent retains the retrieval tool for additional contextual searches.
        fixed_citations = self.knowledge.search(
            f"{request.role} {request.department} mandatory for all employees access policy",
            categories=["role", "training", "policy"],
            k=6,
        )
        safe_profile = {
            "case_id": request.case_id,
            "employee_id": request.employee_id,
            "role": request.role,
            "department": request.department,
            "start_date": request.start_date.isoformat() if request.start_date else None,
            "resume_text": request.resume_text,
            "preferred_language": request.preferred_language,
            "training_format": request.training_format,
            "request": request.request_text,
            "mandatory_retrieved_context": citations_as_context(fixed_citations),
        }
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=json.dumps(safe_profile, ensure_ascii=False))]}
        )
        structured = result.get("structured_response")
        if structured is None:
            raise RuntimeError(f"{self.name} did not return a structured_response")
        worker_result = WorkerResult.model_validate(structured)
        if worker_result.worker != self.name:
            worker_result = worker_result.model_copy(update={"worker": self.name})
        return worker_result


def _extract_delimited_values(text: str, field: str) -> list[str]:
    next_field = r"(?:role|department|required_skills|standard_access|privileged_access)"
    match = re.search(
        rf"{re.escape(field)}:\s*(.*?)(?=\s+{next_field}:|\n|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(";") if part.strip()]


@dataclass
class OfflineSpecialistWorker:
    """Uses the real vector index and business data, but no LLM; for tests only."""

    name: WorkerName
    knowledge: KnowledgeBase

    def run(self, request: OnboardingRequest) -> WorkerResult:
        if self.name == "training":
            citations = self.knowledge.search(
                f"{request.role} required skills {request.resume_text}",
                categories=["role", "training"],
                k=6,
            ) + self.knowledge.search(
                f"all employees mandatory information security onboarding {request.role}",
                categories=["training", "policy"],
                k=6,
            )
            citations = list({citation.source: citation for citation in citations}.values())
            courses = []
            joined = "\n".join(c.excerpt for c in citations)
            for course_id in re.findall(r"course_id:\s*([A-Z]+-\d+)", joined):
                if course_id not in courses:
                    courses.append(course_id)
            courses = courses or ["SEC-101", "COL-100"]
            return WorkerResult(
                worker="training",
                summary="Prepared a cited synthetic training plan from the approved catalogue.",
                recommendations=courses[:4],
                citations=citations,
                structured_data={
                    "day_30": courses[:2],
                    "day_60": courses[2:3],
                    "day_90": courses[3:4],
                },
            )

        if self.name == "hr_documents":
            citations = self.knowledge.search(
                "onboarding human approval data minimization contract notification",
                categories=["policy"],
                k=4,
            )
            return WorkerResult(
                worker="hr_documents",
                summary="Prepared the HR checklist and reversible document drafts for review.",
                recommendations=[
                    "Prepare manager welcome notification",
                    "Prepare onboarding checklist",
                    "Require HR approval before sending",
                ],
                citations=citations,
                structured_data={"status": "DRAFT_ONLY"},
            )

        citations = self.knowledge.search(
            f"{request.role} {request.department} standard access privileged access",
            categories=["role", "policy"],
            k=5,
        )
        joined = "\n".join(c.excerpt for c in citations)
        access = _extract_delimited_values(joined, "standard_access")
        privileged = _extract_delimited_values(joined, "privileged_access")
        risk_flags = [
            f"Privileged access requires additional approval: {item}" for item in privileged
        ]
        return WorkerResult(
            worker="it_provisioning",
            summary="Prepared a least-privilege draft IT access request from the approved matrix.",
            recommendations=access + privileged,
            citations=citations,
            risk_flags=risk_flags,
            structured_data={"requested_access": access + privileged, "status": "DRAFT"},
        )


@dataclass
class WorkerRegistry:
    workers: dict[WorkerName, Worker]

    def run(self, name: WorkerName, request: OnboardingRequest) -> WorkerResult:
        return self.workers[name].run(request)


def build_live_workers(model: BaseChatModel, knowledge: KnowledgeBase) -> WorkerRegistry:
    return WorkerRegistry(
        workers={
            name: LiveSpecialistWorker(name, model, knowledge)
            for name in ("training", "hr_documents", "it_provisioning")
        }
    )


def build_offline_workers(knowledge: KnowledgeBase) -> WorkerRegistry:
    return WorkerRegistry(
        workers={
            name: OfflineSpecialistWorker(name, knowledge)
            for name in ("training", "hr_documents", "it_provisioning")
        }
    )
