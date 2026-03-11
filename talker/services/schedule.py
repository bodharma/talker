"""Schedule service — manage recurring assessments."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.db import ScheduledAssessment, User

log = logging.getLogger(__name__)

RECURRENCE_DAYS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
}


class ScheduleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_schedule(
        self,
        clinician_id: int,
        patient_id: int,
        instruments: list[str],
        recurrence: str = "weekly",
    ) -> ScheduledAssessment:
        days = RECURRENCE_DAYS.get(recurrence, 7)
        sched = ScheduledAssessment(
            clinician_id=clinician_id,
            patient_id=patient_id,
            instruments=instruments,
            recurrence=recurrence,
            next_due=datetime.now() + timedelta(days=days),
        )
        self.db.add(sched)
        await self.db.flush()
        return sched

    async def get_due_assessments(self, patient_id: int) -> list[ScheduledAssessment]:
        """Get assessments that are due now or overdue for a patient."""
        stmt = select(ScheduledAssessment).where(
            ScheduledAssessment.patient_id == patient_id,
            ScheduledAssessment.is_active == True,  # noqa: E712
            ScheduledAssessment.next_due <= datetime.now(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_upcoming(self, patient_id: int) -> list[ScheduledAssessment]:
        """Get all active schedules for a patient."""
        stmt = (
            select(ScheduledAssessment)
            .where(
                ScheduledAssessment.patient_id == patient_id,
                ScheduledAssessment.is_active == True,  # noqa: E712
            )
            .order_by(ScheduledAssessment.next_due)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def mark_completed(self, schedule_id: int) -> None:
        """Mark a scheduled assessment as completed and advance next_due."""
        stmt = select(ScheduledAssessment).where(ScheduledAssessment.id == schedule_id)
        result = await self.db.execute(stmt)
        sched = result.scalar_one_or_none()
        if not sched:
            return
        sched.last_completed = datetime.now()
        days = RECURRENCE_DAYS.get(sched.recurrence, 7)
        sched.next_due = datetime.now() + timedelta(days=days)
        await self.db.flush()

    async def list_for_clinician(self, clinician_id: int) -> list[dict]:
        """List all schedules created by a clinician with patient info."""
        stmt = (
            select(ScheduledAssessment)
            .where(ScheduledAssessment.clinician_id == clinician_id)
            .order_by(ScheduledAssessment.next_due)
        )
        result = await self.db.execute(stmt)
        schedules = result.scalars().all()

        items = []
        for s in schedules:
            user_stmt = select(User).where(User.id == s.patient_id)
            user_result = await self.db.execute(user_stmt)
            patient = user_result.scalar_one_or_none()
            items.append({
                "id": s.id,
                "patient_name": patient.name if patient else "Unknown",
                "patient_email": patient.email if patient else "",
                "instruments": s.instruments,
                "recurrence": s.recurrence,
                "next_due": s.next_due,
                "last_completed": s.last_completed,
                "is_active": s.is_active,
            })
        return items

    async def deactivate(self, schedule_id: int) -> None:
        stmt = select(ScheduledAssessment).where(ScheduledAssessment.id == schedule_id)
        result = await self.db.execute(stmt)
        sched = result.scalar_one_or_none()
        if sched:
            sched.is_active = False
            await self.db.flush()
