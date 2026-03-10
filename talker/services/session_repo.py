import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from talker.models.db import (
    SafetyEventRecord,
    Session,
    SessionConversation,
    SessionScreening,
    SessionSummaryRecord,
)
from talker.models.schemas import (
    ChatMessage,
    ScreeningResult,
    SessionData,
    SessionListItem,
    SessionState,
)

SEVERITY_ORDER = [
    "minimal",
    "none",
    "mild",
    "moderate",
    "moderately severe",
    "severe",
    "above threshold",
]


def _worst_severity(severities: list[str]) -> str:
    if not severities:
        return "none"
    return max(
        severities,
        key=lambda s: SEVERITY_ORDER.index(s) if s in SEVERITY_ORDER else 0,
    )


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        instrument_queue: list[str],
        mode: str = "web",
    ) -> uuid_mod.UUID:
        session = Session(
            state=SessionState.SCREENING,
            mode=mode,
            instrument_queue=instrument_queue,
            current_instrument_index=0,
        )
        self.db.add(session)
        await self.db.flush()
        return session.id

    async def load(self, session_id: uuid_mod.UUID) -> SessionData | None:
        stmt = (
            select(Session)
            .options(
                selectinload(Session.screenings),
                selectinload(Session.conversations),
            )
            .where(Session.id == session_id)
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            return None

        completed_results = [
            ScreeningResult(
                instrument_id=s.instrument_id,
                score=s.score,
                severity=s.severity,
                raw_answers=s.raw_answers,
                flagged_items=s.flagged_items,
            )
            for s in session.screenings
        ]

        chat_messages = [
            ChatMessage(role=c.role, content=c.content) for c in session.conversations
        ]

        return SessionData(
            id=session.id,
            state=SessionState(session.state),
            instrument_queue=session.instrument_queue,
            current_instrument_index=session.current_instrument_index,
            completed_results=completed_results,
            chat_messages=chat_messages,
            current_answers=session.current_answers or {},
            created_at=session.created_at,
        )

    async def update_state(
        self,
        session_id: uuid_mod.UUID,
        state: SessionState,
        instrument_index: int | None = None,
    ) -> None:
        stmt = select(Session).where(Session.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one()
        session.state = state
        if instrument_index is not None:
            session.current_instrument_index = instrument_index
        if state == SessionState.COMPLETED:
            session.completed_at = datetime.utcnow()
        await self.db.flush()

    async def save_screening(
        self, session_id: uuid_mod.UUID, result: ScreeningResult
    ) -> None:
        screening = SessionScreening(
            session_id=session_id,
            instrument_id=result.instrument_id,
            score=result.score,
            severity=result.severity,
            raw_answers=result.raw_answers,
            flagged_items=result.flagged_items,
        )
        self.db.add(screening)
        await self.db.flush()

    async def save_answer(
        self, session_id: uuid_mod.UUID, question_id: str, value: int
    ) -> None:
        stmt = select(Session).where(Session.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one()
        answers = dict(session.current_answers or {})
        answers[question_id] = value
        session.current_answers = answers
        await self.db.flush()

    async def clear_current_answers(self, session_id: uuid_mod.UUID) -> None:
        stmt = select(Session).where(Session.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one()
        session.current_answers = {}
        await self.db.flush()

    async def save_message(
        self, session_id: uuid_mod.UUID, role: str, content: str
    ) -> None:
        msg = SessionConversation(
            session_id=session_id,
            role=role,
            content=content,
        )
        self.db.add(msg)
        await self.db.flush()

    async def save_summary(
        self,
        session_id: uuid_mod.UUID,
        instruments_completed: list[str],
        recommendations: list[str],
        areas_to_explore: list[str] | None = None,
        observations: list[dict] | None = None,
    ) -> None:
        summary = SessionSummaryRecord(
            session_id=session_id,
            instruments_completed=instruments_completed,
            recommendations=recommendations,
            areas_to_explore=areas_to_explore or [],
            observations=observations or [],
        )
        self.db.add(summary)
        await self.db.flush()

    async def save_safety_event(
        self,
        session_id: uuid_mod.UUID,
        trigger: str,
        agent: str,
        message_shown: str,
        resources: list[str],
    ) -> None:
        event = SafetyEventRecord(
            session_id=session_id,
            trigger=trigger,
            agent=agent,
            message_shown=message_shown,
            resources_provided=resources,
        )
        self.db.add(event)
        await self.db.flush()

    async def list_completed(self) -> list[SessionListItem]:
        stmt = (
            select(Session)
            .options(selectinload(Session.screenings))
            .where(
                Session.state.in_(
                    [SessionState.COMPLETED, SessionState.INTERRUPTED_BY_SAFETY]
                )
            )
            .order_by(Session.created_at.desc())
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        items = []
        for s in sessions:
            severities = [sc.severity for sc in s.screenings]
            top = _worst_severity(severities) if severities else None
            items.append(
                SessionListItem(
                    id=s.id,
                    state=s.state,
                    created_at=s.created_at,
                    completed_at=s.completed_at,
                    instruments=[sc.instrument_id for sc in s.screenings],
                    top_severity=top,
                )
            )
        return items

    async def get_detail(self, session_id: uuid_mod.UUID) -> SessionData | None:
        return await self.load(session_id)
