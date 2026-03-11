"""Cross-session memory for conversation continuity."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from talker.models.db import Session, SessionScreening


class SessionMemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_prior_context(self, current_session_id=None, limit: int = 3) -> str:
        """Get summary of recent prior sessions for prompt injection."""
        stmt = (
            select(Session)
            .options(selectinload(Session.screenings))
            .where(Session.state == "completed")
            .order_by(desc(Session.created_at))
            .limit(limit + 1)  # +1 to skip current if included
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        # Filter out current session
        if current_session_id:
            sessions = [s for s in sessions if str(s.id) != str(current_session_id)]
        sessions = sessions[:limit]

        if not sessions:
            return ""

        lines = ["PRIOR SESSION HISTORY (for context — do not repeat previous assessments):"]
        for s in sessions:
            date_str = s.created_at.strftime("%Y-%m-%d")
            instruments: list[str] = []
            screening: SessionScreening
            for screening in s.screenings:
                instruments.append(
                    f"{screening.instrument_id.upper()}: {screening.score} ({screening.severity})"
                )
            scores = ", ".join(instruments) if instruments else "no screenings"
            lines.append(f"- Session {date_str}: {scores}")

        return "\n".join(lines)
