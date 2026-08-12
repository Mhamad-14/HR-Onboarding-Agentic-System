"""Small deterministic and LangSmith-ready evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from langsmith import Client

from .rag import KnowledgeBase


@dataclass(frozen=True)
class RetrievalCase:
    question: str
    expected_source: str
    expected_term: str


RETRIEVAL_CASES = [
    RetrievalCase(
        question="Which course teaches Docker to Software Engineers?",
        expected_source="training_catalog.csv",
        expected_term="ENG-201",
    ),
    RetrievalCase(
        question="What access is standard for a Software Engineer?",
        expected_source="role_competencies.csv",
        expected_term="GitHub",
    ),
    RetrievalCase(
        question="What must happen before privileged access is activated?",
        expected_source="policy_information_security.md",
        expected_term="human approval",
    ),
]


def run_retrieval_smoke_tests(knowledge: KnowledgeBase) -> list[dict]:
    results = []
    for case in RETRIEVAL_CASES:
        citations = knowledge.search(case.question, k=6)
        source_match = any(case.expected_source in item.source for item in citations)
        term_match = any(case.expected_term.lower() in item.excerpt.lower() for item in citations)
        results.append(
            {
                "question": case.question,
                "expected_source": case.expected_source,
                "expected_term": case.expected_term,
                "source_match": source_match,
                "term_match": term_match,
                "passed": source_match and term_match,
            }
        )
    return results


def create_langsmith_dataset(
    client: Client,
    *,
    dataset_name: str = "onboardai-rag-smoke-tests",
) -> str:
    """Create an idempotent LangSmith dataset for the evaluation rubric."""

    if client.has_dataset(dataset_name=dataset_name):
        return dataset_name
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Synthetic retrieval checks for OnboardAI approved HR knowledge.",
    )
    client.create_examples(
        inputs=[{"question": case.question} for case in RETRIEVAL_CASES],
        outputs=[
            {
                "expected_source": case.expected_source,
                "expected_term": case.expected_term,
            }
            for case in RETRIEVAL_CASES
        ],
        dataset_id=dataset.id,
    )
    return dataset_name
