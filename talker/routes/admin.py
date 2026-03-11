# talker/routes/admin.py
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from talker.config import get_settings
from talker.services.admin_repo import AdminRepository, SessionFilter

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/admin")
log = logging.getLogger(__name__)


async def verify_admin(request: Request):
    """Dependency that checks admin session cookie."""
    if not request.session.get("admin_authenticated"):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    settings = get_settings()
    if not settings.admin_password:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


@router.get("/login")
async def admin_login_page(request: Request):
    settings = get_settings()
    if not settings.admin_password:
        return templates.TemplateResponse(
            request=request,
            name="admin/login.html",
            context={"error": "Admin access is disabled. Set ADMIN_PASSWORD in environment."},
        )
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"error": None},
    )


@router.post("/login")
async def admin_login(
    request: Request,
    username: str = Form(),
    password: str = Form(),
):
    settings = get_settings()
    if (
        settings.admin_password
        and username == settings.admin_username
        and password == settings.admin_password
    ):
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"error": "Invalid credentials"},
    )


@router.get("/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


# --- Protected routes ---


@router.get("/", dependencies=[Depends(verify_admin)])
async def admin_sessions(request: Request):
    filters = SessionFilter(
        state=request.query_params.get("state") or None,
        severity=request.query_params.get("severity") or None,
        has_safety_events=request.query_params.get("has_safety") == "1" or None,
        date_from=request.query_params.get("date_from") or None,
        date_to=request.query_params.get("date_to") or None,
        page=int(request.query_params.get("page", "1")),
    )

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        sessions, total = await repo.list_sessions(filters)

    total_pages = (total + filters.per_page - 1) // filters.per_page

    return templates.TemplateResponse(
        request=request,
        name="admin/sessions.html",
        context={
            "sessions": sessions,
            "filters": filters,
            "total": total,
            "total_pages": total_pages,
            "active_page": "sessions",
        },
    )


@router.get("/sessions/{session_id}", dependencies=[Depends(verify_admin)])
async def admin_session_detail(request: Request, session_id: str):
    sid = uuid.UUID(session_id)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        session = await repo.get_session_detail(sid)

    if not session:
        return RedirectResponse(url="/admin/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/session_detail.html",
        context={
            "session": session,
            "active_page": "sessions",
        },
    )


@router.post("/sessions/{session_id}/notes", dependencies=[Depends(verify_admin)])
async def admin_save_notes(
    request: Request,
    session_id: str,
    notes: str = Form(),
):
    sid = uuid.UUID(session_id)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        await repo.save_admin_notes(sid, notes)

    return RedirectResponse(
        url=f"/admin/sessions/{session_id}", status_code=303
    )


@router.get("/safety", dependencies=[Depends(verify_admin)])
async def admin_safety(request: Request):
    date_from = request.query_params.get("date_from") or None
    date_to = request.query_params.get("date_to") or None
    agent = request.query_params.get("agent") or None
    page = int(request.query_params.get("page", "1"))

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        events, total = await repo.list_safety_events(
            date_from=date_from, date_to=date_to, agent=agent, page=page
        )

    total_pages = (total + 49) // 50

    return templates.TemplateResponse(
        request=request,
        name="admin/safety.html",
        context={
            "events": events,
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "date_from": date_from or "",
            "date_to": date_to or "",
            "agent": agent or "",
            "active_page": "safety",
        },
    )


@router.get("/stats", dependencies=[Depends(verify_admin)])
async def admin_stats(request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        stats = await repo.get_stats()

    return templates.TemplateResponse(
        request=request,
        name="admin/stats.html",
        context={"stats": stats, "active_page": "stats"},
    )


@router.get("/knowledge", dependencies=[Depends(verify_admin)])
async def admin_knowledge(request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        try:
            docs = await repo.get_knowledge_docs()
        except Exception:
            docs = []  # pgvector not available

    return templates.TemplateResponse(
        request=request,
        name="admin/knowledge.html",
        context={
            "documents": docs,
            "active_page": "knowledge",
            "message": request.query_params.get("message"),
        },
    )


@router.post("/knowledge/reingest", dependencies=[Depends(verify_admin)])
async def admin_reingest(request: Request):
    from talker.services.embeddings import EmbeddingService
    from talker.services.ingest import ingest_documents

    settings = get_settings()
    if not settings.openai_api_key:
        return RedirectResponse(
            url="/admin/knowledge?message=No+embedding+API+key+configured",
            status_code=303,
        )

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        emb = EmbeddingService(settings)
        try:
            count = await ingest_documents("talker/knowledge", db, emb)
            msg = f"Success:+Ingested+{count}+chunks"
        except Exception as e:
            msg = f"Error:+{str(e)[:100]}"

    return RedirectResponse(
        url=f"/admin/knowledge?message={msg}", status_code=303
    )


# --- Export routes ---


@router.get("/export/json", dependencies=[Depends(verify_admin)])
async def admin_export_json(request: Request):
    """Export all sessions as JSON."""
    from talker.services.export import ExportService

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        svc = ExportService(db)
        data = await svc.export_all_json()

    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=talker-export.json"
        },
    )


@router.get("/export/csv", dependencies=[Depends(verify_admin)])
async def admin_export_csv(request: Request):
    """Export all sessions as CSV."""
    from talker.services.export import ExportService

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        svc = ExportService(db)
        csv_data = await svc.export_sessions_csv()

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=talker-export.csv"
        },
    )


@router.get("/sessions/{session_id}/export", dependencies=[Depends(verify_admin)])
async def admin_export_session(request: Request, session_id: str):
    """Export single session as JSON."""
    from talker.services.export import ExportService

    sid = uuid.UUID(session_id)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        svc = ExportService(db)
        data = await svc.export_session_json(sid)

    if not data:
        return RedirectResponse(url="/admin/", status_code=303)

    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f"attachment; filename=session-{session_id[:8]}.json"
            )
        },
    )
