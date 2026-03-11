import logging

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from talker.config import Settings
from talker.models.db import Base

log = logging.getLogger(__name__)


async def _has_pgvector(engine) -> bool:
    """Check if pgvector extension is available without aborting the transaction."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        return True
    except Exception:
        log.warning("pgvector not available, knowledge tables will be skipped")
        return False


@pytest_asyncio.fixture
async def db_session():
    settings = Settings()
    engine = create_async_engine(settings.database_url)

    has_vector = await _has_pgvector(engine)

    async with engine.begin() as conn:
        if has_vector:
            import talker.models.knowledge  # noqa: F401

            await conn.run_sync(Base.metadata.create_all)
        else:
            import talker.models.knowledge as km

            exclude = {
                km.KnowledgeDocument.__table__,
                km.KnowledgeChunk.__table__,
            }
            tables = [t for t in Base.metadata.sorted_tables if t not in exclude]
            for table in tables:
                await conn.run_sync(
                    lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True)
                )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()
