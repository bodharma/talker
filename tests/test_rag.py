from talker.services.rag import RAGService, RetrievalResult


def test_retrieval_result_model():
    result = RetrievalResult(
        content="PHQ-9 measures depression severity",
        heading="Depression Screening",
        source_type="psychoeducation",
        source_file="depression.md",
        similarity=0.89,
    )
    assert result.similarity == 0.89
    assert "depression" in result.content.lower()


def test_format_context():
    results = [
        RetrievalResult(
            content="PHQ-9 scores range from 0-27.",
            heading="Scoring",
            source_type="psychoeducation",
            source_file="phq9.md",
            similarity=0.92,
        ),
        RetrievalResult(
            content="Moderate depression (10-14) may benefit from therapy.",
            heading="Treatment",
            source_type="clinical",
            source_file="depression.md",
            similarity=0.85,
        ),
    ]
    context = RAGService.format_context(results)
    assert "PHQ-9 scores" in context
    assert "Moderate depression" in context
    assert "---" in context


def test_format_context_empty():
    context = RAGService.format_context([])
    assert context == ""


def test_format_context_single():
    results = [
        RetrievalResult(
            content="CBT is effective.",
            heading="Treatment",
            source_type="clinical",
            source_file="treatment.md",
            similarity=0.9,
        ),
    ]
    context = RAGService.format_context(results)
    assert "CBT" in context
    assert "---" not in context
