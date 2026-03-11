"""RAG retrieval service with pgvector semantic search."""

from pydantic import BaseModel
from sqlalchemy import select
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

        stmt = (
            select(
                KnowledgeChunk.content,
                KnowledgeChunk.heading,
                KnowledgeDocument.source_type,
                KnowledgeDocument.source_file,
                KnowledgeChunk.embedding.cosine_distance(query_embedding).label(
                    "distance"
                ),
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
                similarity=1 - row.distance,
            )
            for row in rows
        ]

    @staticmethod
    def format_context(results: list[RetrievalResult]) -> str:
        """Format retrieval results into a text context block for LLM prompts."""
        if not results:
            return ""

        sections = []
        for r in results:
            section = f"[{r.source_type}] {r.heading}\n{r.content}"
            sections.append(section)

        return "\n---\n".join(sections)
