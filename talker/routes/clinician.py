"""Clinician dashboard routes."""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from talker.models.db import PatientLink, Session, User
from talker.routes.deps import verify_clinician
from talker.services.invite import InviteService

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/clinician")
log = logging.getLogger(__name__)


@router.get("/", dependencies=[Depends(verify_clinician)])
async def clinician_patients(request: Request):
    user_id = request.session["user_id"]
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        stmt = (
            select(PatientLink)
            .where(PatientLink.clinician_id == user_id)
        )
        result = await db.execute(stmt)
        links = result.scalars().all()

        patients = []
        for link in links:
            user_stmt = select(User).where(User.id == link.patient_id)
            user_result = await db.execute(user_stmt)
            patient = user_result.scalar_one_or_none()
            if patient:
                session_stmt = select(Session).where(Session.user_id == patient.id)
                session_result = await db.execute(session_stmt)
                session_count = len(session_result.scalars().all())
                patients.append({
                    "id": patient.id,
                    "name": patient.name,
                    "email": patient.email,
                    "session_count": session_count,
                    "linked_at": link.created_at,
                })

    return templates.TemplateResponse(
        request=request,
        name="clinician/patients.html",
        context={"patients": patients, "active_page": "patients"},
    )


@router.get("/patients/{patient_id}", dependencies=[Depends(verify_clinician)])
async def clinician_patient_detail(request: Request, patient_id: int):
    user_id = request.session["user_id"]
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        link_stmt = select(PatientLink).where(
            PatientLink.clinician_id == user_id,
            PatientLink.patient_id == patient_id,
        )
        link_result = await db.execute(link_stmt)
        if not link_result.scalar_one_or_none():
            return RedirectResponse(url="/clinician/", status_code=303)

        user_stmt = select(User).where(User.id == patient_id)
        user_result = await db.execute(user_stmt)
        patient = user_result.scalar_one_or_none()

        session_stmt = (
            select(Session)
            .options(selectinload(Session.screenings))
            .where(Session.user_id == patient_id)
            .order_by(Session.created_at.desc())
        )
        session_result = await db.execute(session_stmt)
        sessions = session_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="clinician/patient_detail.html",
        context={
            "patient": patient,
            "sessions": sessions,
            "active_page": "patients",
        },
    )


@router.get("/invite", dependencies=[Depends(verify_clinician)])
async def clinician_invite_page(request: Request):
    user_id = request.session["user_id"]
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        svc = InviteService(db)
        invites = await svc.list_invites(user_id)

    return templates.TemplateResponse(
        request=request,
        name="clinician/invite.html",
        context={
            "invites": invites,
            "active_page": "invite",
            "message": request.query_params.get("message"),
        },
    )


@router.post("/invite", dependencies=[Depends(verify_clinician)])
async def clinician_create_invite(
    request: Request,
    email: str = Form(),
    instruments: str = Form(default=""),
):
    from talker.config import get_settings

    user_id = request.session["user_id"]
    instrument_list = [i.strip() for i in instruments.split(",") if i.strip()] or None

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        svc = InviteService(db)
        invite = await svc.create_invite(
            clinician_id=user_id,
            email=email,
            instruments=instrument_list,
        )
        await db.commit()

    settings = get_settings()
    invite_url = f"{settings.base_url}/auth/invite/{invite.token}"
    msg = f"Invite+created.+Send+this+link:+{invite_url}"
    return RedirectResponse(
        url=f"/clinician/invite?message={msg}", status_code=303
    )
