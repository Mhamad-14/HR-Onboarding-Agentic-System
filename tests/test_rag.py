from onboardai.rag import DeterministicHashEmbeddings, KnowledgeBase


def test_rag_indexes_and_retrieves_role_and_training(project_root):
    knowledge = KnowledgeBase.build(
        project_root / "data" / "knowledge", DeterministicHashEmbeddings()
    )
    assert len(knowledge.chunks) > 4
    results = knowledge.search("Software Engineer Docker course and standard access", k=6)
    combined = " ".join(citation.excerpt for citation in results)
    assert "ENG-201" in combined
    assert "GitHub" in combined
    assert all(citation.source for citation in results)


def test_rag_category_filter_is_enforced(project_root):
    knowledge = KnowledgeBase.build(
        project_root / "data" / "knowledge", DeterministicHashEmbeddings()
    )
    results = knowledge.search("human approval", categories=["policy"], k=4)
    assert results
    assert {result.category for result in results} == {"policy"}
