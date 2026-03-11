from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from talker.models.db import Invite, PatientLink

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()


@router.get("/")
async def index(request: Request):
    assigned = None
    user_id = request.session.get("user_id")
    if user_id:
        session_factory = request.app.state.db_session_factory
        async with session_factory() as db:
            stmt = (
                select(Invite)
                .join(PatientLink, PatientLink.clinician_id == Invite.clinician_id)
                .where(
                    PatientLink.patient_id == user_id,
                    Invite.instruments.isnot(None),
                    Invite.accepted_at.isnot(None),
                )
                .order_by(Invite.created_at.desc())
                .limit(1)
            )
            result = await db.execute(stmt)
            invite = result.scalar_one_or_none()
            if invite and invite.instruments:
                assigned = invite.instruments

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"recent_sessions": [], "assigned_instruments": assigned},
    )
