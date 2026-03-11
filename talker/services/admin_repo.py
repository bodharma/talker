"""Admin-specific database queries for session auditing and stats."""

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from talker.models.db import (
    SafetyEventRecord,
    Session,
    SessionScreening,
)


class SessionFilter(BaseModel):
    state: str | None = None
    severity: str | None = None
    has_safety_events: bool | None = None
    date_from: str | None = None
    date_to: str | None = None
    page: int = 1
    per_page: int = 25


class SessionListItem(BaseModel):
    id: str
    created_at: datetime
    state: str
    instruments: list[str]
    highest_severity: str
    safety_event_count: int


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sessions(self, filters: SessionFilter) -> tuple[list[SessionListItem], int]:
        """List sessions with filtering and pagination. Returns (items, total_count)."""
        stmt = (
            select(Session)
            .options(
                selectinload(Session.screenings),
                selectinload(Session.safety_events),
            )
            .order_by(desc(Session.created_at))
        )

        if filters.state:
            stmt = stmt.where(Session.state == filters.state)
        if filters.date_from:
            stmt = stmt.where(Session.created_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(Session.created_at <= filters.date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        items = []
        severity_order = [
            "severe", "moderately severe", "above threshold", "moderate", "mild", "minimal",
        ]
        for s in sessions:
            instruments = [sc.instrument_id for sc in s.screenings]
            severities = [sc.severity for sc in s.screenings]
            highest = "none"
            for sev in severity_order:
                if sev in severities:
                    highest = sev
                    break

            safety_count = len(s.safety_events)

            if filters.severity and highest != filters.severity:
                continue
            if filters.has_safety_events and safety_count == 0:
                continue

            items.append(SessionListItem(
                id=str(s.id),
                created_at=s.created_at,
                state=s.state,
                instruments=instruments,
                highest_severity=highest,
                safety_event_count=safety_count,
            ))

        return items, total

    async def get_session_detail(self, session_id: uuid_mod.UUID) -> Session | None:
        """Get full session with all related data for audit."""
        stmt = (
            select(Session)
            .where(Session.id == session_id)
            .options(
                selectinload(Session.screenings),
                selectinload(Session.conversations),
                selectinload(Session.safety_events),
                selectinload(Session.voice_features),
                selectinload(Session.summary),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_admin_notes(self, session_id: uuid_mod.UUID, notes: str) -> None:
        """Save admin notes for a session."""
        stmt = select(Session).where(Session.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if session:
            existing = session.admin_notes or {}
            existing["notes"] = notes
            existing["updated_at"] = datetime.now().isoformat()
            session.admin_notes = existing
            await self.db.commit()

    async def list_safety_events(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        agent: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[dict], int]:
        """List all safety events across sessions."""
        stmt = (
            select(SafetyEventRecord)
            .order_by(desc(SafetyEventRecord.created_at))
        )

        if date_from:
            stmt = stmt.where(SafetyEventRecord.created_at >= date_from)
        if date_to:
            stmt = stmt.where(SafetyEventRecord.created_at <= date_to)
        if agent:
            stmt = stmt.where(SafetyEventRecord.agent == agent)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [
            {
                "id": e.id,
                "session_id": str(e.session_id),
                "trigger": e.trigger,
                "agent": e.agent,
                "message_shown": e.message_shown,
                "resources": e.resources_provided,
                "created_at": e.created_at,
            }
            for e in events
        ], total

    async def get_stats(self) -> dict:
        """Get system-wide statistics."""
        total = (await self.db.execute(select(func.count(Session.id)))).scalar() or 0

        state_stmt = (
            select(Session.state, func.count(Session.id))
            .group_by(Session.state)
        )
        state_result = await self.db.execute(state_stmt)
        states = {row[0]: row[1] for row in state_result.all()}

        completed = states.get("completed", 0)
        completion_rate = round(completed / total * 100, 1) if total else 0

        safety_count = (
            await self.db.execute(select(func.count(SafetyEventRecord.id)))
        ).scalar() or 0

        score_stmt = (
            select(
                SessionScreening.instrument_id,
                func.avg(SessionScreening.score).label("avg_score"),
                func.count(SessionScreening.id).label("count"),
            )
            .group_by(SessionScreening.instrument_id)
        )
        score_result = await self.db.execute(score_stmt)
        avg_scores = [
            {
                "instrument_id": row.instrument_id,
                "avg_score": round(float(row.avg_score), 1),
                "count": row.count,
            }
            for row in score_result.all()
        ]

        return {
            "total_sessions": total,
            "completed_sessions": completed,
            "completion_rate": completion_rate,
            "safety_event_count": safety_count,
            "sessions_by_state": states,
            "avg_scores": avg_scores,
        }

    async def get_knowledge_docs(self) -> list[dict]:
        """List knowledge documents with chunk counts."""
        from talker.models.knowledge import KnowledgeChunk, KnowledgeDocument

        stmt = (
            select(
                KnowledgeDocument.id,
                KnowledgeDocument.title,
                KnowledgeDocument.source_type,
                KnowledgeDocument.source_file,
                KnowledgeDocument.created_at,
                func.count(KnowledgeChunk.id).label("chunk_count"),
            )
            .outerjoin(KnowledgeChunk)
            .group_by(KnowledgeDocument.id)
            .order_by(KnowledgeDocument.source_type, KnowledgeDocument.title)
        )
        result = await self.db.execute(stmt)
        return [
            {
                "id": row.id,
                "title": row.title,
                "source_type": row.source_type,
                "source_file": row.source_file,
                "created_at": row.created_at,
                "chunk_count": row.chunk_count,
            }
            for row in result.all()
        ]
