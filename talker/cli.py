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
