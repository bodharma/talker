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


@pytest.mark.asyncio
async def test_update_state(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"])
    await repo.update_state(session_id, SessionState.FOLLOW_UP, instrument_index=1)
    data = await repo.load(session_id)
    assert data.state == SessionState.FOLLOW_UP
    assert data.current_instrument_index == 1


@pytest.mark.asyncio
async def test_save_screening(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"])
    result = ScreeningResult(
        instrument_id="phq-9",
        score=14,
        severity="moderate",
        raw_answers={"q1": 2, "q2": 1},
        flagged_items=[9],
    )
    await repo.save_screening(session_id, result)
    data = await repo.load(session_id)
    assert len(data.completed_results) == 1
    assert data.completed_results[0].instrument_id == "phq-9"
    assert data.completed_results[0].score == 14


@pytest.mark.asyncio
async def test_save_and_clear_answers(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"])
    await repo.save_answer(session_id, "q1", 2)
    await repo.save_answer(session_id, "q2", 1)
    data = await repo.load(session_id)
    assert data.current_answers == {"q1": 2, "q2": 1}

    await repo.clear_current_answers(session_id)
    data = await repo.load(session_id)
    assert data.current_answers == {}


@pytest.mark.asyncio
async def test_save_message(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"])
    await repo.save_message(session_id, "assistant", "Hello")
    await repo.save_message(session_id, "user", "Hi there")
    data = await repo.load(session_id)
    assert len(data.chat_messages) == 2
    assert data.chat_messages[0].role == "assistant"
    assert data.chat_messages[1].content == "Hi there"


@pytest.mark.asyncio
async def test_save_summary(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"])
    await repo.save_summary(
        session_id,
        instruments_completed=["phq-9"],
        recommendations=["Consider therapy"],
    )
    await repo.update_state(session_id, SessionState.COMPLETED)
    data = await repo.load(session_id)
    assert data.state == SessionState.COMPLETED


@pytest.mark.asyncio
async def test_save_safety_event(db_session):
    repo = SessionRepository(db_session)
    session_id = await repo.create(instrument_queue=["phq-9"])
    await repo.save_safety_event(
        session_id,
        trigger="kill myself",
        agent="screener",
        message_shown="crisis message",
        resources=["988 Lifeline"],
    )
    # Verify it doesn't raise — event is persisted


@pytest.mark.asyncio
async def test_list_completed(db_session):
    repo = SessionRepository(db_session)
    sid = await repo.create(instrument_queue=["phq-9"])
    result = ScreeningResult(
        instrument_id="phq-9",
        score=5,
        severity="mild",
        raw_answers={},
        flagged_items=[],
    )
    await repo.save_screening(sid, result)
    await repo.update_state(sid, SessionState.COMPLETED)
    await db_session.commit()

    sessions = await repo.list_completed()
    assert len(sessions) >= 1
    found = [s for s in sessions if s.id == sid]
    assert len(found) == 1
    assert found[0].instruments == ["phq-9"]
