# Talker RAG System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add retrieval-augmented generation to provide grounded clinical knowledge, psychoeducation, and resource recommendations across all agents.

**Architecture:** pgvector for embeddings stored in PostgreSQL. Embedding via OpenAI API (cloud) or Ollama nomic-embed-text (local). Markdown knowledge documents chunked and indexed. RAG results injected into agent system prompts.

**Tech Stack:** pgvector, SQLAlchemy (pgvector extension), OpenAI embeddings API / Ollama, markdown chunking, PydanticAI tool integration.

**Spec:** `docs/specs/2026-03-10-talker-design.md` — RAG System and Agentic Tool-Calling sections.

**Prerequisites:** Phase 1 must be complete (agents, instruments, web UI working).

---

## Chunk 1: Vector Store Foundation

### Task 1: pgvector Setup & Embedding Models

**Files:**
- Modify: `pyproject.toml` (add pgvector, openai dependencies)
- Modify: `talker/config.py` (add RAG settings)
- Create: `talker/services/embeddings.py`
- Create: `talker/models/knowledge.py`
- Modify: `talker/models/db.py` (add knowledge tables)
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Add to `dependencies`:
```
"pgvector>=0.3.0",
"openai>=1.50.0",
```

- [ ] **Step 2: Add RAG config to Settings**

```python
# Add to talker/config.py Settings class:

# RAG
embedding_provider: str = "openai"  # "openai" or "ollama"
openai_api_key: str = ""  # for embeddings only
embedding_model: str = "text-embedding-3-small"
ollama_embedding_model: str = "nomic-embed-text"
ollama_base_url: str = "http://localhost:11434"
rag_chunk_size: int = 512
rag_chunk_overlap: int = 64
rag_top_k: int = 5
```

- [ ] **Step 3: Write tests for embedding service**

```python
# tests/test_embeddings.py
import pytest
from unittest.mock import AsyncMock, patch
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
    assert "Section One" in chunks[0].text


def test_chunk_markdown_respects_max_size():
    text = "word " * 200  # ~1000 chars
    chunks = chunk_markdown(text, max_size=100)
    assert all(len(c.text) <= 150 for c in chunks)  # some margin for splitting


def test_chunk_has_metadata():
    text = """# Depression
PHQ-9 is a screening tool."""
    chunks = chunk_markdown(text, max_size=500)
    assert chunks[0].heading == "Depression"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_embeddings.py -v`
Expected: FAIL

- [ ] **Step 5: Implement embedding service**

```python
# talker/services/embeddings.py
from dataclasses import dataclass, field

from talker.config import Settings


@dataclass
class TextChunk:
    text: str
    heading: str = ""
    source_file: str = ""
    metadata: dict = field(default_factory=dict)


def chunk_markdown(
    text: str,
    max_size: int = 512,
    overlap: int = 64,
) -> list[TextChunk]:
    """Split markdown by headers, then by size if needed."""
    import re

    sections = re.split(r'^(#{1,3}\s+.+)$', text, flags=re.MULTILINE)
    chunks = []
    current_heading = ""

    i = 0
    while i < len(sections):
        section = sections[i].strip()
        if not section:
            i += 1
            continue

        if re.match(r'^#{1,3}\s+', section):
            current_heading = re.sub(r'^#{1,3}\s+', '', section).strip()
            i += 1
            continue

        # Split large sections by paragraph then by size
        if len(section) <= max_size:
            chunks.append(TextChunk(text=section, heading=current_heading))
        else:
            paragraphs = section.split('\n\n')
            buffer = ""
            for para in paragraphs:
                if len(buffer) + len(para) + 2 > max_size:
                    if buffer:
                        chunks.append(TextChunk(text=buffer.strip(), heading=current_heading))
                    buffer = para
                else:
                    buffer = buffer + "\n\n" + para if buffer else para
            if buffer:
                chunks.append(TextChunk(text=buffer.strip(), heading=current_heading))

        i += 1

    return chunks


class EmbeddingService:
    """Generates embeddings via OpenAI API or Ollama."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.embedding_provider

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "openai":
            return await self._embed_openai(texts)
        else:
            return await self._embed_ollama(texts)

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        import openai
        client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        response = await client.embeddings.create(
            input=texts,
            model=self.settings.embedding_model,
        )
        return [item.embedding for item in response.data]

    async def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        import httpx
        embeddings = []
        async with httpx.AsyncClient() as client:
            for text in texts:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/embeddings",
                    json={"model": self.settings.ollama_embedding_model, "prompt": text},
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
        return embeddings
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_embeddings.py -v`
Expected: PASS

- [ ] **Step 7: Create knowledge SQLAlchemy models**

```python
# talker/models/knowledge.py
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from talker.models.db import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_file: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50))  # clinical, psychoeducation, resource
    title: Mapped[str] = mapped_column(String(500))
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="document")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"))
    heading: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))  # text-embedding-3-small dimension
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")
```

- [ ] **Step 8: Generate Alembic migration**

Run: `uv run alembic revision --autogenerate -m "add knowledge tables with pgvector"`

Note: Requires `CREATE EXTENSION IF NOT EXISTS vector;` in the migration's `upgrade()`.

- [ ] **Step 9: Commit**

```bash
git add talker/services/embeddings.py talker/models/knowledge.py talker/config.py pyproject.toml migrations/ tests/test_embeddings.py
git commit -m "feat: embedding service and knowledge base models with pgvector"
```

---

### Task 2: RAG Retrieval Service

**Files:**
- Create: `talker/services/rag.py`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write tests for RAG service**

```python
# tests/test_rag.py
import pytest
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
    assert "---" in context  # separator between results
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rag.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RAG service**

```python
# talker/services/rag.py
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.knowledge import KnowledgeChunk, KnowledgeDocument
from talker.services.embeddings import EmbeddingService


class RetrievalResult(BaseModel):
    content: str
    heading: str
    source_type: str
    source_file: str
    similarity: float


class RAGService:
    """Retrieves relevant knowledge chunks via semantic search."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def retrieve(
        self,
        query: str,
        db: AsyncSession,
        top_k: int = 5,
        source_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Semantic search over knowledge base."""
        embeddings = await self.embedding_service.embed([query])
        query_embedding = embeddings[0]

        # Build pgvector similarity query
        stmt = (
            select(
                KnowledgeChunk.content,
                KnowledgeChunk.heading,
                KnowledgeDocument.source_type,
                KnowledgeDocument.source_file,
                KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(KnowledgeDocument)
            .order_by("distance")
            .limit(top_k)
        )

        if source_type:
            stmt = stmt.where(KnowledgeDocument.source_type == source_type)

        result = await db.execute(stmt)
        rows = result.all()

        return [
            RetrievalResult(
                content=row.content,
                heading=row.heading,
                source_type=row.source_type,
                source_file=row.source_file,
                similarity=1 - row.distance,  # cosine_distance to similarity
            )
            for row in rows
        ]

    @staticmethod
    def format_context(results: list[RetrievalResult]) -> str:
        """Format retrieval results into a text context block for LLM prompts."""
        if not results:
            return "No relevant knowledge found."

        sections = []
        for r in results:
            section = f"[{r.source_type}] {r.heading}\n{r.content}"
            sections.append(section)

        return "\n---\n".join(sections)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rag.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talker/services/rag.py tests/test_rag.py
git commit -m "feat: RAG retrieval service with pgvector semantic search"
```

---

## Chunk 2: Knowledge Base Content

### Task 3: Knowledge Document Ingestion Pipeline

**Files:**
- Create: `talker/services/ingest.py`
- Create: `talker/cli.py` (CLI commands for ingestion)
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write tests for ingestion**

```python
# tests/test_ingest.py
import pytest
from pathlib import Path
from talker.services.ingest import scan_knowledge_dir, prepare_chunks


def test_scan_knowledge_dir(tmp_path):
    # Create test markdown files
    clinical = tmp_path / "clinical"
    clinical.mkdir()
    (clinical / "depression.md").write_text("# Depression\nContent about depression.")
    (clinical / "anxiety.md").write_text("# Anxiety\nContent about anxiety.")

    docs = scan_knowledge_dir(str(tmp_path))
    assert len(docs) == 2
    types = {d.source_type for d in docs}
    assert "clinical" in types


def test_prepare_chunks():
    from talker.services.ingest import RawDocument

    doc = RawDocument(
        source_file="clinical/depression.md",
        source_type="clinical",
        title="Depression",
        content="# Depression\nPHQ-9 is used for screening.\n\n## Treatment\nCBT is effective.",
    )
    chunks = prepare_chunks(doc, max_size=500)
    assert len(chunks) >= 1
    assert any("PHQ-9" in c.text for c in chunks)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ingestion pipeline**

```python
# talker/services/ingest.py
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.knowledge import KnowledgeDocument, KnowledgeChunk
from talker.services.embeddings import EmbeddingService, TextChunk, chunk_markdown


@dataclass
class RawDocument:
    source_file: str
    source_type: str
    title: str
    content: str


def scan_knowledge_dir(base_dir: str) -> list[RawDocument]:
    """Scan knowledge directory for markdown files, organized by type."""
    base = Path(base_dir)
    docs = []

    for type_dir in sorted(base.iterdir()):
        if not type_dir.is_dir():
            continue
        source_type = type_dir.name  # clinical, psychoeducation, resources

        for md_file in sorted(type_dir.glob("*.md")):
            content = md_file.read_text()
            title = md_file.stem.replace("-", " ").replace("_", " ").title()
            docs.append(RawDocument(
                source_file=str(md_file.relative_to(base)),
                source_type=source_type,
                title=title,
                content=content,
            ))

    return docs


def prepare_chunks(doc: RawDocument, max_size: int = 512) -> list[TextChunk]:
    """Chunk a document into embeddable pieces."""
    chunks = chunk_markdown(doc.content, max_size=max_size)
    for chunk in chunks:
        chunk.source_file = doc.source_file
        chunk.metadata = {"source_type": doc.source_type, "title": doc.title}
    return chunks


async def ingest_documents(
    base_dir: str,
    db: AsyncSession,
    embedding_service: EmbeddingService,
    max_chunk_size: int = 512,
    batch_size: int = 50,
) -> int:
    """Full ingestion pipeline: scan → chunk → embed → store."""
    raw_docs = scan_knowledge_dir(base_dir)
    total_chunks = 0

    for raw_doc in raw_docs:
        # Create document record
        doc = KnowledgeDocument(
            source_file=raw_doc.source_file,
            source_type=raw_doc.source_type,
            title=raw_doc.title,
        )
        db.add(doc)
        await db.flush()  # get doc.id

        # Chunk and embed
        chunks = prepare_chunks(raw_doc, max_size=max_chunk_size)
        texts = [c.text for c in chunks]

        # Embed in batches
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = await embedding_service.embed(batch)
            all_embeddings.extend(embeddings)

        # Store chunks
        for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
            db_chunk = KnowledgeChunk(
                document_id=doc.id,
                heading=chunk.heading,
                content=chunk.text,
                chunk_index=idx,
                embedding=embedding,
            )
            db.add(db_chunk)

        total_chunks += len(chunks)

    await db.commit()
    return total_chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Create CLI command for ingestion**

```python
# talker/cli.py
"""CLI commands for Talker management."""

import asyncio
import click

from talker.config import Settings
from talker.services.database import create_session_factory
from talker.services.embeddings import EmbeddingService
from talker.services.ingest import ingest_documents


@click.group()
def cli():
    """Talker CLI management commands."""
    pass


@cli.command()
@click.argument("knowledge_dir", default="talker/knowledge")
def ingest(knowledge_dir: str):
    """Ingest knowledge documents into the RAG vector store."""

    async def _run():
        settings = Settings()
        session_factory = create_session_factory(settings)
        embedding_service = EmbeddingService(settings)

        async with session_factory() as db:
            count = await ingest_documents(
                knowledge_dir, db, embedding_service
            )
            click.echo(f"Ingested {count} chunks from {knowledge_dir}")

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
```

- [ ] **Step 6: Commit**

```bash
git add talker/services/ingest.py talker/cli.py tests/test_ingest.py
git commit -m "feat: knowledge document ingestion pipeline with CLI"
```

---

### Task 4: Seed Knowledge Content

**Files:**
- Create: `talker/knowledge/clinical/depression.md`
- Create: `talker/knowledge/clinical/anxiety.md`
- Create: `talker/knowledge/clinical/ptsd.md`
- Create: `talker/knowledge/clinical/adhd.md`
- Create: `talker/knowledge/clinical/comorbidity.md`
- Create: `talker/knowledge/psychoeducation/phq-9-guide.md`
- Create: `talker/knowledge/psychoeducation/gad-7-guide.md`
- Create: `talker/knowledge/psychoeducation/pcl-5-guide.md`
- Create: `talker/knowledge/psychoeducation/asrs-guide.md`
- Create: `talker/knowledge/psychoeducation/treatment-approaches.md`
- Create: `talker/knowledge/resources/crisis-resources.md`
- Create: `talker/knowledge/resources/finding-a-therapist.md`

NOTE: Content for these files should be researched and written using authoritative sources (NIMH, APA, WHO). Use deep research tools to gather accurate, current clinical information. Each file should be 500-2000 words of well-structured markdown.

- [ ] **Step 1: Research and write clinical knowledge documents**

Use deep research to gather authoritative content on:
- Depression: DSM-5 criteria, subtypes, differential diagnosis
- Anxiety: GAD criteria, panic vs generalized, somatic symptoms
- PTSD: trauma types, symptom clusters, complex PTSD
- ADHD: adult presentation, inattentive vs hyperactive, differential
- Comorbidity: common co-occurrences, how they interact

- [ ] **Step 2: Write psychoeducation guides for each instrument**

Each guide should explain:
- What the instrument measures
- What each score range means in practical terms
- What to expect from a professional evaluation
- Self-care strategies appropriate for each severity level

- [ ] **Step 3: Write resource documents**

- Crisis resources: international hotlines, when to seek emergency help
- Finding a therapist: what to look for, types of therapy, questions to ask

- [ ] **Step 4: Run ingestion**

Run: `uv run python -m talker.cli ingest talker/knowledge`
Expected: Output showing chunks ingested per document

- [ ] **Step 5: Commit**

```bash
git add talker/knowledge/
git commit -m "feat: seed clinical, psychoeducation, and resource knowledge base"
```

---

## Chunk 3: Agent Integration

### Task 5: Wire RAG into Conversation Agent

**Files:**
- Modify: `talker/agents/conversation.py`
- Create: `talker/agents/rag_tools.py`
- Test: `tests/test_rag_tools.py`

- [ ] **Step 1: Write tests for RAG-powered tools**

```python
# tests/test_rag_tools.py
import pytest
from talker.agents.rag_tools import build_rag_enhanced_prompt


def test_build_rag_enhanced_prompt_includes_context():
    rag_context = "[psychoeducation] PHQ-9 Scoring\nScores above 10 suggest moderate depression."
    base_prompt = "You are a mental health assistant."
    enhanced = build_rag_enhanced_prompt(base_prompt, rag_context)
    assert "CLINICAL KNOWLEDGE" in enhanced
    assert "PHQ-9 Scoring" in enhanced
    assert "mental health assistant" in enhanced


def test_build_rag_enhanced_prompt_no_context():
    enhanced = build_rag_enhanced_prompt("Base prompt.", "")
    assert "CLINICAL KNOWLEDGE" not in enhanced
    assert "Base prompt." in enhanced
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rag_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RAG-enhanced prompts**

```python
# talker/agents/rag_tools.py
"""RAG-powered tool functions for agents."""


def build_rag_enhanced_prompt(base_prompt: str, rag_context: str) -> str:
    """Enhance an agent's system prompt with RAG-retrieved knowledge."""
    if not rag_context or rag_context == "No relevant knowledge found.":
        return base_prompt

    return f"""{base_prompt}

CLINICAL KNOWLEDGE (use this to inform your responses, but do not quote directly):
{rag_context}"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rag_tools.py -v`
Expected: PASS

- [ ] **Step 5: Update Conversation Agent to use RAG context**

Modify `talker/agents/conversation.py` — add a method:

```python
def build_system_prompt_with_rag(self, context: ConversationContext, rag_context: str) -> str:
    """Build system prompt enhanced with RAG-retrieved knowledge."""
    from talker.agents.rag_tools import build_rag_enhanced_prompt
    base = self.build_system_prompt(context)
    return build_rag_enhanced_prompt(base, rag_context)
```

- [ ] **Step 6: Update assess routes to use RAG in conversation**

In `talker/routes/assess.py`, update `_get_llm_response` to:
1. Query RAG service with the user's message + screening context
2. Format RAG results into context string
3. Pass to `build_system_prompt_with_rag`

```python
# In _get_llm_response, before creating the agent:
rag_context = ""
if hasattr(request.app.state, "rag_service"):
    rag_service = request.app.state.rag_service
    db = ...  # get from app state
    results = await rag_service.retrieve(user_message, db, top_k=3)
    rag_context = RAGService.format_context(results)

system_prompt = orch.conversation.build_system_prompt_with_rag(ctx, rag_context)
```

- [ ] **Step 7: Commit**

```bash
git add talker/agents/rag_tools.py talker/agents/conversation.py talker/routes/assess.py tests/test_rag_tools.py
git commit -m "feat: RAG-enhanced conversation agent with clinical knowledge retrieval"
```

---

### Task 6: Clinical Context Tool for Agents

**Files:**
- Modify: `talker/agents/tools.py`
- Test: `tests/test_tools.py` (add RAG tool tests)

- [ ] **Step 1: Add test for get_clinical_context tool**

```python
# Add to tests/test_tools.py:

def test_build_clinical_query():
    from talker.agents.tools import build_clinical_query
    query = build_clinical_query(
        symptoms=["insomnia", "low mood", "fatigue"],
        instrument_id="phq-9",
    )
    assert "insomnia" in query
    assert "phq-9" in query.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools.py::test_build_clinical_query -v`
Expected: FAIL

- [ ] **Step 3: Implement clinical context tool**

Add to `talker/agents/tools.py`:

```python
def build_clinical_query(
    symptoms: list[str],
    instrument_id: str | None = None,
) -> str:
    """Build a query for RAG retrieval of clinical context."""
    query = f"Clinical information about: {', '.join(symptoms)}"
    if instrument_id:
        query += f" (related to {instrument_id.upper()} screening)"
    return query
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tools.py::test_build_clinical_query -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talker/agents/tools.py tests/test_tools.py
git commit -m "feat: clinical context tool for RAG-powered symptom exploration"
```

---

### Task 7: Final Integration & Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `uv run ruff check talker/ tests/`
Expected: No errors

- [ ] **Step 3: Integration test — full RAG flow**

1. Start PostgreSQL with pgvector extension
2. Run migrations: `uv run alembic upgrade head`
3. Ingest knowledge: `uv run python -m talker.cli ingest talker/knowledge`
4. Start app: `uv run uvicorn talker.main:app --reload --port 8000`
5. Run an assessment — during conversation, ask "What does my PHQ-9 score mean?"
6. Verify the response references grounded clinical knowledge (not just LLM training data)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: RAG system complete — clinical knowledge, psychoeducation, and resource retrieval"
```
