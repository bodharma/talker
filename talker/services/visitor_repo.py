"""Repository for visitor tracking — used by receptionist persona."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.db import Visitor, VisitorLog


class VisitorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_email(self, email: str) -> Visitor | None:
        result = await self.db.execute(
            select(Visitor).where(Visitor.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def find_by_name(self, first_name: str, last_name: str) -> Visitor | None:
        result = await self.db.execute(
            select(Visitor).where(
                Visitor.first_name.ilike(first_name.strip()),
                Visitor.last_name.ilike(last_name.strip()),
            )
        )
        return result.scalar_one_or_none()

    async def register(
        self,
        first_name: str,
        last_name: str,
        email: str,
        company: str | None = None,
    ) -> Visitor:
        existing = await self.find_by_email(email)
        if existing:
            existing.first_name = first_name.strip()
            existing.last_name = last_name.strip()
            if company:
                existing.company = company.strip()
            await self.db.flush()
            return existing

        visitor = Visitor(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.lower().strip(),
            company=company.strip() if company else None,
        )
        self.db.add(visitor)
        await self.db.flush()
        return visitor

    async def log_visit(
        self,
        visitor_id: int,
        visiting_person: str,
        visiting_company: str,
        floor: int,
        mood_impression: str | None = None,
        notes: str | None = None,
    ) -> VisitorLog:
        visit = VisitorLog(
            visitor_id=visitor_id,
            visiting_person=visiting_person,
            visiting_company=visiting_company,
            floor=floor,
            mood_impression=mood_impression,
            notes=notes,
        )
        self.db.add(visit)

        # Update visitor stats
        result = await self.db.execute(
            select(Visitor).where(Visitor.id == visitor_id)
        )
        visitor = result.scalar_one()
        visitor.visit_count += 1
        visitor.last_visit_at = datetime.now(timezone.utc)

        await self.db.flush()
        return visit

    async def get_visit_history(self, visitor_id: int, limit: int = 5) -> list[VisitorLog]:
        result = await self.db.execute(
            select(VisitorLog)
            .where(VisitorLog.visitor_id == visitor_id)
            .order_by(VisitorLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
