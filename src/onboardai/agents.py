"""Track A Supervisor + Workers and the Orchestrator-Worker planner/synthesizer."""

from __future__ import annotations

import json
from typing import Literal, Protocol

from langchain.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from .grounding import ground_worker_result
from .rag import KnowledgeBase, citations_as_context
from .schemas import (
    Citation,
    OnboardingRequest,
    SupervisorDecision,
    SupervisorPlan,
    SynthesisResult,
    WorkerAssignment,
    WorkerName,
    WorkerResult,
)


class Supervisor(Protocol):
    def plan(self, request: OnboardingRequest) -> SupervisorPlan: ...
    def route_once(
        self,
        *,
        request_text: str,
        role: str,
        department: str,
        available_workers: list[WorkerName],
    ) -> SupervisorDecision: ...
    def synthesize(
        self,
        request: OnboardingRequest,
        results: dict[str, WorkerResult],
    ) -> SynthesisResult: ...


class Worker(Protocol):
    name: WorkerName
    def run(self, request: OnboardingRequest) -> WorkerResult: ...


PLAN_PROMPT = """
You are the dedicated HR onboarding supervisor in a Track A Supervisor + Workers architecture.
Your job is orchestration, not specialist execution.

Break the requested post-hire onboarding work into specialist assignments.
Available workers:
- training: skill-gap analysis and cited approved training
- hr_documents: onboarding-policy review and reversible HR document drafts
- it_provisioning: least-privilege role-based access planning

Rules:
1. Include every worker explicitly listed in requested_actions exactly once.
2. Do not include an unrequested worker.
3. Give each worker a concrete objective tied to the employee role and user request.
4. Never use protected characteristics.
5. Do not invent HR policy, course IDs, or access names.
""".strip()


ROUTING_PROMPT = """
You are a routing-only HR supervisor. Choose exactly one best specialist for the user's request.
Choose from the provided available workers. Route by meaning, not by keyword matching.
training = learning plan and skill gaps
hr_documents = onboarding policy and draft HR communications
it_provisioning = system access, accounts, equipment, least privilege
""".strip()


SYNTHESIS_PROMPT = """
You are the synthesizer in an Orchestrator-Worker workflow.
Summarize only the supplied worker outputs. Do not add new policy, course IDs, access names,
legal terms, salary terms, or actions. Mention key risks that a human reviewer should see.
""".strip()


class StructuredSupervisor:
    """LLM supervisor using Pydantic structured output for planning, routing, and synthesis."""

    def __init__(self, model: BaseChatModel):
        self.plan_model = model.with_structured_output(SupervisorPlan)
        self.route_model = model.with_structured_output(SupervisorDecision)
        self.synthesis_model = model.with_structured_output(SynthesisResult)

    @staticmethod
    def _plan_error(plan: SupervisorPlan, requested: list[WorkerName]) -> str | None:
        planned = [assignment.worker for assignment in plan.assignments]
        if len(planned) != len(set(planned)):
            return "The plan contains a duplicate worker."
        if set(planned) != set(requested):
            return (
                f"The plan must contain exactly these workers: {requested}. "
                f"It returned: {planned}."
            )
        return None

    def plan(self, request: OnboardingRequest) -> SupervisorPlan:
        feedback = ""
        for attempt in range(3):
            prompt = (
                f"{PLAN_PROMPT}\n\n"
                f"Employee role: {request.role}\n"
                f"Department: {request.department}\n"
                f"User request: {request.request_text}\n"
                f"requested_actions: {request.requested_actions}"
                f"{feedback}"
            )
            plan = self.plan_model.invoke(prompt)
            error = self._plan_error(plan, request.requested_actions)
            if error is None:
                return plan
            print(
                f"[supervisor-plan] invalid structured plan on attempt #{attempt + 1}; "
                "looping back with validation feedback"
            )
            feedback = (
                "\n\nYour previous structured plan was rejected by Python validation: "
                f"{error} Correct the plan."
            )
        raise RuntimeError("Supervisor could not produce a valid constrained plan")

    def route_once(
        self,
        *,
        request_text: str,
        role: str,
        department: str,
        available_workers: list[WorkerName],
    ) -> SupervisorDecision:
        return self.route_model.invoke(
            f"{ROUTING_PROMPT}\n\n"
            f"Role: {role}\nDepartment: {department}\n"
            f"Available workers: {available_workers}\n"
            f"User request: {request_text}"
        )

    def synthesize(
        self,
        request: OnboardingRequest,
        results: dict[str, WorkerResult],
    ) -> SynthesisResult:
        payload = {
            name: result.model_dump(mode="json")
            for name, result in results.items()
        }
        synthesis = self.synthesis_model.invoke(
            f"{SYNTHESIS_PROMPT}\n\n"
            f"Employee role: {request.role}\n"
            f"Worker outputs:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        actual_risks = sorted(
            {flag for result in results.values() for flag in result.risk_flags}
        )
        actual_sources = {
            citation.source
            for result in results.values()
            for citation in result.citations
        }
        return synthesis.model_copy(
            update={
                "completed_workers": list(results),
                "key_risks": actual_risks,
                "source_count": len(actual_sources),
            }
        )


class OfflineSupervisor:
    """Deterministic test double. Never use this output as live LLM-routing evidence."""

    def plan(self, request: OnboardingRequest) -> SupervisorPlan:
        return SupervisorPlan(
            assignments=[
                WorkerAssignment(
                    worker=worker,
                    objective=f"Complete the requested {worker} onboarding subtask.",
                )
                for worker in request.requested_actions
            ],
            rationale="Offline test adapter mirrors the requested specialist set.",
        )

    def route_once(
        self,
        *,
        request_text: str,
        role: str,
        department: str,
        available_workers: list[WorkerName],
    ) -> SupervisorDecision:
        return SupervisorDecision(
            destination=available_workers[0],
            reason="Offline test adapter; not grading evidence for model-driven routing.",
            confidence="low",
        )

    def synthesize(
        self,
        request: OnboardingRequest,
        results: dict[str, WorkerResult],
    ) -> SynthesisResult:
        risks = sorted({flag for result in results.values() for flag in result.risk_flags})
        sources = {citation.source for result in results.values() for citation in result.citations}
        return SynthesisResult(
            summary="Offline synthesis combined all completed specialist results for human review.",
            completed_workers=list(results),
            key_risks=risks,
            source_count=len(sources),
        )


def _build_retrieval_tool(knowledge: KnowledgeBase):
    @tool
    def search_approved_onboarding_knowledge(
        query: str,
        categories: list[Literal["policy", "role", "training"]],
    ) -> str:
        """Semantic-search approved HR policy, role matrix, and training catalogue evidence."""

        citations = knowledge.search(query, categories=list(categories), k=5)
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
You are the Training Specialist Agent.
You MUST call search_approved_onboarding_knowledge before the final response.
Search role requirements, training catalogue, and relevant policy.
Return approved course IDs only. Compare only job-relevant resume skills with retrieved evidence.
Cite material claims and include a proposed 30/60/90-day plan in structured_data.
Never invent a course ID.
""".strip(),
    "hr_documents": """
You are the HR Documents Specialist Agent.
You MUST call search_approved_onboarding_knowledge before the final response.
Retrieve onboarding and data-minimization policy.
Recommend reversible draft documents and review steps only. Do not claim a document was sent,
legally approved, or signed. Cite the retrieved policy evidence.
""".strip(),
    "it_provisioning": """
You are the IT Provisioning Specialist Agent.
You MUST call search_approved_onboarding_knowledge before the final response.
Retrieve the exact role-to-access row and the security policy.
Put requested access in structured_data.requested_access.
Flag privileged access. Never activate an account and never reveal or request credentials.
""".strip(),
}


def _actual_tool_citations(messages: list[object]) -> tuple[list[Citation], int]:
    citations: list[Citation] = []
    retrieval_tool_call_count = 0

    for message in messages:
        for tool_call in getattr(message, "tool_calls", []) or []:
            name = tool_call.get("name")
            print(
                "[MODEL TOOL CALL] "
                f"name={name} args={tool_call.get('args')}"
            )
            if name == "search_approved_onboarding_knowledge":
                retrieval_tool_call_count += 1

        if isinstance(message, ToolMessage):
            content = message.content
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                continue
            for item in payload.get("citations", []):
                try:
                    citations.append(Citation.model_validate(item))
                except Exception:
                    continue

    unique: dict[str, Citation] = {}
    for citation in citations:
        unique[citation.source] = citation
    return list(unique.values()), retrieval_tool_call_count


class LiveSpecialistWorker:
    """Live specialist with an explicit retrieval phase followed by structured output.

    Why two phases?
    With provider-native structured output, the model can sometimes emit the WorkerResult
    schema immediately instead of using the retrieval tool. The capstone needs visible,
    genuine tool-call evidence, so retrieval is made an explicit LLM tool-calling phase.

    The LLM still generates the semantic search query/categories. The tool then performs
    real vector retrieval before a second structured-output call creates WorkerResult.
    """

    def __init__(self, name: WorkerName, model: BaseChatModel, knowledge: KnowledgeBase):
        self.name = name
        self.knowledge = knowledge
        self.model = model
        self.retrieval_tool = _build_retrieval_tool(knowledge)

        # LangChain's model interface supports forcing an actual tool call with tool_choice="any".
        # This avoids the model skipping retrieval in favor of immediately emitting WorkerResult.
        self.retrieval_model = model.bind_tools(
            [self.retrieval_tool],
            tool_choice="any",
        )
        self.structured_model = model.with_structured_output(WorkerResult)

    def _run_agentic_retrieval(self, safe_profile: dict) -> tuple[list[Citation], str]:
        retrieval_messages = [
            SystemMessage(
                content=(
                    WORKER_PROMPTS[self.name]
                    + "\n\nRETRIEVAL PHASE: Before producing any worker result, issue a "
                    "semantic-search tool call. Create a useful query and choose the relevant "
                    "categories from policy, role, and training. Do not answer the onboarding "
                    "task in this phase."
                )
            ),
            HumanMessage(content=json.dumps(safe_profile, ensure_ascii=False)),
        ]

        ai_message = self.retrieval_model.invoke(retrieval_messages)
        tool_calls = getattr(ai_message, "tool_calls", []) or []

        retrieval_calls = [
            call
            for call in tool_calls
            if call.get("name") == self.retrieval_tool.name
        ]
        if not retrieval_calls:
            raise RuntimeError(
                f"{self.name} did not emit the required retrieval tool call"
            )

        all_citations: list[Citation] = []
        contexts: list[str] = []

        for call in retrieval_calls:
            print(
                "[MODEL RETRIEVAL TOOL CALL] "
                f"name={call.get('name')} args={call.get('args')}"
            )

            # Execute the actual LangChain tool with the LLM-generated arguments.
            raw_result = self.retrieval_tool.invoke(call.get("args", {}))
            if not isinstance(raw_result, str):
                raw_result = str(raw_result)

            try:
                payload = json.loads(raw_result)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"{self.name} retrieval tool returned non-JSON output"
                ) from exc

            contexts.append(str(payload.get("context", "")))
            for item in payload.get("citations", []):
                all_citations.append(Citation.model_validate(item))

        # De-duplicate by source while preserving order.
        unique: dict[str, Citation] = {}
        for citation in all_citations:
            unique.setdefault(citation.source, citation)

        return list(unique.values()), "\n\n".join(contexts)

    def run(self, request: OnboardingRequest) -> WorkerResult:
        # Hybrid RAG:
        # 1) deterministic retrieval guarantees mandatory evidence;
        # 2) a genuine LLM-issued tool call performs contextual semantic retrieval.
        fixed_citations = self.knowledge.search(
            f"{request.role} {request.department} mandatory training standard access human approval",
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

        actual_citations, agentic_context = self._run_agentic_retrieval(safe_profile)

        structured_prompt = (
            WORKER_PROMPTS[self.name]
            + "\n\nThe semantic retrieval step has already been completed. "
            "Use ONLY the supplied employee data and retrieved evidence below. "
            "Return the required WorkerResult structure. Do not invent policy, "
            "course IDs, access names, or missing fields.\n\n"
            f"EMPLOYEE INPUT:\n{json.dumps(safe_profile, ensure_ascii=False, indent=2)}\n\n"
            f"AGENTIC RETRIEVAL RESULT:\n{agentic_context}"
        )

        structured = self.structured_model.invoke(
            [
                SystemMessage(content=WORKER_PROMPTS[self.name]),
                HumanMessage(content=structured_prompt),
            ]
        )
        worker_result = WorkerResult.model_validate(structured)

        if worker_result.worker != self.name:
            worker_result = worker_result.model_copy(update={"worker": self.name})

        citation_map = {citation.source: citation for citation in fixed_citations}
        for citation in actual_citations:
            citation_map[citation.source] = citation

        worker_result = worker_result.model_copy(
            update={"citations": list(citation_map.values())}
        )

        # Final identifiers are deterministically validated against approved source files.
        return ground_worker_result(
            request,
            worker_result,
            self.knowledge.knowledge_dir,
        )


class OfflineSpecialistWorker:
    """Real RAG + deterministic worker used only for tests and non-LLM error demos."""

    def __init__(self, name: WorkerName, knowledge: KnowledgeBase):
        self.name = name
        self.knowledge = knowledge

    def run(self, request: OnboardingRequest) -> WorkerResult:
        if self.name == "training":
            citations = self.knowledge.search(
                f"{request.role} Docker testing mandatory training",
                categories=["role", "training", "policy"],
                k=7,
            )
            base = WorkerResult(
                worker="training",
                summary="Offline test adapter generated a training proposal from retrieved evidence.",
                recommendations=["DOCKER-101", "ENG-201"],
                citations=citations,
                structured_data={},
            )
            return ground_worker_result(request, base, self.knowledge.knowledge_dir)

        if self.name == "hr_documents":
            citations = self.knowledge.search(
                "onboarding human approval data minimization draft documents",
                categories=["policy"],
                k=4,
            )
            base = WorkerResult(
                worker="hr_documents",
                summary="Offline test adapter prepared reversible HR draft actions.",
                citations=citations,
            )
            return ground_worker_result(request, base, self.knowledge.knowledge_dir)

        citations = self.knowledge.search(
            f"{request.role} standard access privileged access security",
            categories=["role", "policy"],
            k=5,
        )
        base = WorkerResult(
            worker="it_provisioning",
            summary="Offline test adapter prepared an access proposal from role evidence.",
            recommendations=["invented-access"],
            citations=citations,
        )
        return ground_worker_result(request, base, self.knowledge.knowledge_dir)


class WorkerRegistry:
    def __init__(self, workers: dict[WorkerName, Worker]):
        self.workers = workers

    def run(self, name: WorkerName, request: OnboardingRequest) -> WorkerResult:
        return self.workers[name].run(request)


def build_live_workers(model: BaseChatModel, knowledge: KnowledgeBase) -> WorkerRegistry:
    return WorkerRegistry(
        {
            name: LiveSpecialistWorker(name, model, knowledge)
            for name in ("training", "hr_documents", "it_provisioning")
        }
    )


def build_offline_workers(knowledge: KnowledgeBase) -> WorkerRegistry:
    return WorkerRegistry(
        {
            name: OfflineSpecialistWorker(name, knowledge)
            for name in ("training", "hr_documents", "it_provisioning")
        }
    )
