"""Session data export in JSON and CSV formats."""

import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from talker.models.db import Session


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_session_json(self, session_id) -> dict | None:
        """Export a single session as JSON-serializable dict."""
        session = await self._load_full_session(session_id)
        if not session:
            return None

        return {
            "id": str(session.id),
            "state": session.state,
            "mode": session.mode,
            "created_at": session.created_at.isoformat(),
            "completed_at": (
                session.completed_at.isoformat() if session.completed_at else None
            ),
            "screenings": [
                {
                    "instrument_id": s.instrument_id,
                    "score": s.score,
                    "severity": s.severity,
                    "raw_answers": s.raw_answers,
                    "flagged_items": s.flagged_items,
                    "created_at": s.created_at.isoformat(),
                }
                for s in session.screenings
            ],
            "conversations": [
                {
                    "role": c.role,
                    "content": c.content,
                    "created_at": c.created_at.isoformat(),
                }
                for c in session.conversations
            ],
            "safety_events": [
                {
                    "trigger": e.trigger,
                    "agent": e.agent,
                    "message_shown": e.message_shown,
                    "resources_provided": e.resources_provided,
                    "created_at": e.created_at.isoformat(),
                }
                for e in session.safety_events
            ],
            "summary": (
                {
                    "instruments_completed": session.summary.instruments_completed,
                    "recommendations": session.summary.recommendations,
                    "areas_to_explore": session.summary.areas_to_explore,
                    "observations": session.summary.observations,
                }
                if session.summary
                else None
            ),
            "voice_features": [
                {
                    "utterance_index": vf.utterance_index,
                    "role": vf.role,
                    "features": vf.features,
                }
                for vf in session.voice_features
            ],
        }

    async def export_sessions_csv(self, session_ids: list | None = None) -> str:
        """Export sessions as CSV (summary rows, one per session)."""
        if session_ids:
            sessions = []
            for sid in session_ids:
                s = await self._load_full_session(sid)
                if s:
                    sessions.append(s)
        else:
            stmt = (
                select(Session)
                .options(
                    selectinload(Session.screenings),
                    selectinload(Session.safety_events),
                )
                .order_by(Session.created_at)
            )
            result = await self.db.execute(stmt)
            sessions = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "session_id",
            "state",
            "mode",
            "created_at",
            "completed_at",
            "instruments",
            "scores",
            "severities",
            "safety_event_count",
        ])
        for s in sessions:
            instruments = [sc.instrument_id for sc in s.screenings]
            scores = [str(sc.score) for sc in s.screenings]
            severities = [sc.severity for sc in s.screenings]
            writer.writerow([
                str(s.id),
                s.state,
                s.mode,
                s.created_at.isoformat(),
                s.completed_at.isoformat() if s.completed_at else "",
                "|".join(instruments),
                "|".join(scores),
                "|".join(severities),
                len(s.safety_events),
            ])
        return output.getvalue()

    async def export_all_json(self) -> list[dict]:
        """Export all sessions as JSON array."""
        stmt = select(Session.id).order_by(Session.created_at)
        result = await self.db.execute(stmt)
        ids = [row[0] for row in result.all()]
        sessions = []
        for sid in ids:
            data = await self.export_session_json(sid)
            if data:
                sessions.append(data)
        return sessions

    async def _load_full_session(self, session_id):
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
