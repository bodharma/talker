"""Longitudinal trend analysis -- symptom scores over time."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.db import Session, SessionScreening

log = logging.getLogger(__name__)


class TrendService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_score_history(
        self, user_id: int, instrument_id: str | None = None
    ) -> list[dict]:
        """Get chronological score history for a user, optionally filtered by instrument."""
        stmt = (
            select(SessionScreening, Session.created_at.label("session_date"))
            .join(Session, Session.id == SessionScreening.session_id)
            .where(Session.user_id == user_id)
            .order_by(Session.created_at)
        )
        if instrument_id:
            stmt = stmt.where(SessionScreening.instrument_id == instrument_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        history = []
        for screening, session_date in rows:
            history.append(
                {
                    "date": session_date.strftime("%Y-%m-%d"),
                    "instrument_id": screening.instrument_id,
                    "score": screening.score,
                    "severity": screening.severity,
                }
            )
        return history

    async def get_trend_summary(self, user_id: int) -> dict:
        """Get a summary of trends per instrument -- latest score, direction, session count."""
        history = await self.get_score_history(user_id)

        by_instrument: dict[str, list[dict]] = {}
        for entry in history:
            by_instrument.setdefault(entry["instrument_id"], []).append(entry)

        summaries = {}
        for inst_id, entries in by_instrument.items():
            latest = entries[-1]
            previous = entries[-2] if len(entries) >= 2 else None
            if previous:
                if latest["score"] > previous["score"]:
                    direction = "worsening"
                elif latest["score"] < previous["score"]:
                    direction = "improving"
                else:
                    direction = "stable"
            else:
                direction = "baseline"

            summaries[inst_id] = {
                "latest_score": latest["score"],
                "latest_severity": latest["severity"],
                "latest_date": latest["date"],
                "direction": direction,
                "session_count": len(entries),
                "scores": [e["score"] for e in entries],
                "dates": [e["date"] for e in entries],
            }
        return summaries

    async def get_chart_data(self, user_id: int) -> dict:
        """Get data formatted for Chart.js line chart."""
        history = await self.get_score_history(user_id)

        by_instrument: dict[str, list[dict]] = {}
        for entry in history:
            by_instrument.setdefault(entry["instrument_id"], []).append(entry)

        datasets = []
        colors = ["#4f46e5", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2"]
        for i, (inst_id, entries) in enumerate(by_instrument.items()):
            color = colors[i % len(colors)]
            datasets.append(
                {
                    "label": inst_id.upper(),
                    "data": [{"x": e["date"], "y": e["score"]} for e in entries],
                    "borderColor": color,
                    "backgroundColor": color + "20",
                    "tension": 0.3,
                    "fill": False,
                }
            )

        return {"datasets": datasets}
