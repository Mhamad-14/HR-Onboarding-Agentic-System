"""Deterministic retrieval checks used as RAG evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .rag import KnowledgeBase


@dataclass(frozen=True)
class RetrievalCase:
    question: str
    expected_source: str
    expected_term: str


RETRIEVAL_CASES = [
    RetrievalCase(
        question="Which approved course teaches Docker to Software Engineers?",
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
        citations = knowledge.search(case.question, k=7)
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
