import uuid
from datetime import datetime

import pytest

from talker.models.schemas import ScreeningResult, SessionData, SessionState
from talker.services.report import render_report_html
from talker.services.session_repo import SessionRepository


def _make_session(**kwargs) -> SessionData:
    defaults = {
        "id": uuid.uuid4(),
        "state": SessionState.COMPLETED,
        "instrument_queue": ["phq-9"],
        "current_instrument_index": 0,
        "completed_results": [],
        "chat_messages": [],
        "current_answers": {},
        "created_at": datetime(2026, 3, 10, 14, 30),
    }
    defaults.update(kwargs)
    return SessionData(**defaults)


def test_render_report_html_basic():
    session = _make_session(
        completed_results=[
            ScreeningResult(
                instrument_id="phq-9",
                score=14,
                severity="moderate",
                raw_answers={"q1": 2},
                flagged_items=[9],
            ),
        ],
    )
    html = render_report_html(
        session=session,
        instrument_names={"phq-9": "Patient Health Questionnaire (PHQ-9)"},
        recommendations=["Consider consulting a mental health professional."],
    )
    assert "Talker Assessment Report" in html
    assert "Patient Health Questionnaire (PHQ-9)" in html
    assert "14" in html
    assert "moderate" in html.lower()
    assert "Flagged items" in html
    assert "Consider consulting" in html


def test_render_report_html_no_results():
    session = _make_session()
    html = render_report_html(
        session=session,
        instrument_names={},
        recommendations=["Your scores are in the minimal range."],
    )
    assert "Talker Assessment Report" in html
    assert "Your scores are in the minimal range." in html


def test_render_report_html_with_safety_events():
    session = _make_session()
    html = render_report_html(
        session=session,
        instrument_names={},
        recommendations=[],
        safety_events=[
            {"trigger": "test trigger", "message_shown": "crisis resources shown"},
        ],
    )
    assert "Safety Events" in html
    assert "test trigger" in html


def test_render_report_html_with_conversation():
    from talker.models.schemas import ChatMessage

    session = _make_session(
        chat_messages=[
            ChatMessage(role="assistant", content="How are you feeling?"),
            ChatMessage(role="user", content="Not great."),
        ],
    )
    html = render_report_html(
        session=session,
        instrument_names={},
        recommendations=[],
    )
    assert "Conversation Summary" in html
    assert "How are you feeling?" in html
    assert "Not great." in html


@pytest.mark.asyncio
async def test_get_recommendations(db_session):
    repo = SessionRepository(db_session)
    sid = await repo.create(instrument_queue=["phq-9"])
    await repo.save_summary(
        sid,
        instruments_completed=["phq-9"],
        recommendations=["See a therapist", "Exercise regularly"],
    )

    recs = await repo.get_recommendations(sid)
    assert recs == ["See a therapist", "Exercise regularly"]


@pytest.mark.asyncio
async def test_get_recommendations_none(db_session):
    repo = SessionRepository(db_session)
    sid = await repo.create(instrument_queue=["phq-9"])

    recs = await repo.get_recommendations(sid)
    assert recs == []


@pytest.mark.asyncio
async def test_get_safety_events(db_session):
    repo = SessionRepository(db_session)
    sid = await repo.create(instrument_queue=["phq-9"])
    await repo.save_safety_event(
        sid,
        trigger="kill myself",
        agent="conversation",
        message_shown="Please call 988",
        resources=["988 Lifeline"],
    )

    events = await repo.get_safety_events(sid)
    assert len(events) == 1
    assert events[0]["trigger"] == "kill myself"
    assert "988" in events[0]["message_shown"]


@pytest.mark.asyncio
async def test_get_safety_events_empty(db_session):
    repo = SessionRepository(db_session)
    sid = await repo.create(instrument_queue=["phq-9"])

    events = await repo.get_safety_events(sid)
    assert events == []
