"""Invite service — create invitations, accept them, link patients."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.db import Invite, PatientLink
from talker.services.auth import AuthService

log = logging.getLogger(__name__)


class InviteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_invite(
        self,
        clinician_id: int,
        email: str,
        instruments: list[str] | None = None,
        schedule: dict | None = None,
        expires_days: int = 7,
    ) -> Invite:
        token = AuthService.generate_token()
        invite = Invite(
            clinician_id=clinician_id,
            email=email,
            token=token,
            instruments=instruments,
            schedule=schedule,
            expires_at=datetime.now() + timedelta(days=expires_days),
        )
        self.db.add(invite)
        await self.db.flush()
        return invite

    async def get_invite_by_token(self, token: str) -> Invite | None:
        stmt = select(Invite).where(
            Invite.token == token,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def accept_invite(self, token: str, patient_id: int) -> bool:
        invite = await self.get_invite_by_token(token)
        if not invite:
            return False

        invite.accepted_at = datetime.now()

        link = PatientLink(
            clinician_id=invite.clinician_id,
            patient_id=patient_id,
        )
        self.db.add(link)
        await self.db.flush()

        log.info(
            "Invite accepted: patient %d linked to clinician %d",
            patient_id,
            invite.clinician_id,
        )
        return True

    async def list_invites(self, clinician_id: int) -> list[Invite]:
        stmt = (
            select(Invite)
            .where(Invite.clinician_id == clinician_id)
            .order_by(Invite.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
