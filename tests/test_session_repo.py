import uuid

import pytest

from talker.models.schemas import ScreeningResult, SessionState
from talker.services.session_repo import SessionRepository


@pytest.mark.asyncio
async def test_create_session(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(
        instrument_queue=["phq-9", "gad-7"],
        mode="web",
    )
    assert session_id is not None


@pytest.mark.asyncio
async def test_load_session(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"], mode="web")
    data = await repo.load(session_id)
    assert data is not None
    assert data.state == SessionState.SCREENING
    assert data.instrument_queue == ["phq-9"]
    assert data.current_instrument_index == 0
    assert data.completed_results == []
    assert data.chat_messages == []


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none(db_session):
    repo = SessionRepository(db_session)
    data = await repo.load(uuid.uuid4())
    assert data is None
