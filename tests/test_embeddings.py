from talker.services.embeddings import EmbeddingService, chunk_markdown


def test_chunk_markdown_by_headers():
    text = """# Section One
Some content here.

## Subsection
More content.

# Section Two
Different topic."""
    chunks = chunk_markdown(text, max_size=500)
    assert len(chunks) >= 2
    assert "Section One" in chunks[0].heading or "content" in chunks[0].text


def test_chunk_markdown_respects_max_size():
    text = "word " * 200  # ~1000 chars
    chunks = chunk_markdown(text, max_size=100)
    assert all(len(c.text) <= 150 for c in chunks)


def test_chunk_has_metadata():
    text = """# Depression
PHQ-9 is a screening tool."""
    chunks = chunk_markdown(text, max_size=500)
    assert chunks[0].heading == "Depression"


def test_chunk_empty_text():
    chunks = chunk_markdown("", max_size=500)
    assert chunks == []


def test_chunk_no_headers():
    text = "Just plain text without any headers."
    chunks = chunk_markdown(text, max_size=500)
    assert len(chunks) == 1
    assert chunks[0].heading == ""
    assert "plain text" in chunks[0].text


def test_embedding_service_init():
    from talker.config import Settings

    settings = Settings(openai_api_key="test-key")
    service = EmbeddingService(settings)
    assert service.provider == "openai"


def test_embedding_service_ollama_provider():
    from talker.config import Settings

    settings = Settings(embedding_provider="ollama")
    service = EmbeddingService(settings)
    assert service.provider == "ollama"
