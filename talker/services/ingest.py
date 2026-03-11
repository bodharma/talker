"""Knowledge document ingestion pipeline: scan → chunk → embed → store."""

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.knowledge import KnowledgeChunk, KnowledgeDocument
from talker.services.embeddings import EmbeddingService, TextChunk, chunk_markdown

log = logging.getLogger(__name__)


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
        source_type = type_dir.name

        for md_file in sorted(type_dir.glob("*.md")):
            content = md_file.read_text()
            title = md_file.stem.replace("-", " ").replace("_", " ").title()
            docs.append(
                RawDocument(
                    source_file=str(md_file.relative_to(base)),
                    source_type=source_type,
                    title=title,
                    content=content,
                )
            )

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
    """Full ingestion pipeline: scan → chunk → embed → store.

    Clears existing documents before re-ingesting.
    """
    # Clear existing data
    await db.execute(delete(KnowledgeChunk))
    await db.execute(delete(KnowledgeDocument))

    raw_docs = scan_knowledge_dir(base_dir)
    total_chunks = 0

    for raw_doc in raw_docs:
        doc = KnowledgeDocument(
            source_file=raw_doc.source_file,
            source_type=raw_doc.source_type,
            title=raw_doc.title,
        )
        db.add(doc)
        await db.flush()

        chunks = prepare_chunks(raw_doc, max_size=max_chunk_size)
        texts = [c.text for c in chunks]

        # Embed in batches
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await embedding_service.embed(batch)
            all_embeddings.extend(embeddings)

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
        log.info(
            "Ingested %s: %d chunks", raw_doc.source_file, len(chunks)
        )

    await db.commit()
    return total_chunks
