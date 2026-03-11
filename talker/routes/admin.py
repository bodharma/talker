# talker/routes/admin.py
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from livekit import api

from talker.config import get_settings
from talker.routes.deps import verify_admin
from talker.services.admin_repo import AdminRepository, SessionFilter

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/admin")
log = logging.getLogger(__name__)


@router.get("/login")
async def admin_login_redirect(request: Request):
    return RedirectResponse(url="/auth/login", status_code=303)


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


async def _fetch_langfuse_metrics() -> dict | None:
    """Fetch daily metrics from Langfuse API (last 30 days)."""
    settings = get_settings()
    if not settings.langfuse_secret_key:
        return None

    import httpx
    from datetime import datetime, timedelta, timezone

    base_url = settings.langfuse_host.rstrip("/")
    from_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base_url}/api/public/metrics/daily",
                params={"fromTimestamp": from_ts, "limit": 30},
                auth=(settings.langfuse_public_key, settings.langfuse_secret_key),
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
    except Exception as e:
        log.warning("Failed to fetch Langfuse metrics: %s", e)
        return None

    total_cost = sum(d.get("totalCost", 0) or 0 for d in data)
    total_traces = sum(d.get("countTraces", 0) or 0 for d in data)
    total_observations = sum(d.get("countObservations", 0) or 0 for d in data)

    # Aggregate per-model usage
    model_usage: dict[str, dict] = {}
    daily_costs = []
    for d in data:
        daily_costs.append({"date": d["date"], "cost": d.get("totalCost", 0) or 0})
        for u in d.get("usage", []):
            model = u.get("model", "unknown")
            if model not in model_usage:
                model_usage[model] = {"input": 0, "output": 0, "total": 0, "cost": 0.0, "traces": 0}
            model_usage[model]["input"] += u.get("inputUsage", 0) or 0
            model_usage[model]["output"] += u.get("outputUsage", 0) or 0
            model_usage[model]["total"] += u.get("totalUsage", 0) or 0
            model_usage[model]["cost"] += u.get("totalCost", 0) or 0
            model_usage[model]["traces"] += u.get("countTraces", 0) or 0

    return {
        "total_cost": round(total_cost, 4),
        "total_traces": total_traces,
        "total_observations": total_observations,
        "model_usage": model_usage,
        "daily_costs": sorted(daily_costs, key=lambda x: x["date"]),
    }


@router.get("/stats", dependencies=[Depends(verify_admin)])
async def admin_stats(request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = AdminRepository(db)
        stats = await repo.get_stats()

    langfuse = await _fetch_langfuse_metrics()

    return templates.TemplateResponse(
        request=request,
        name="admin/stats.html",
        context={
            "stats": stats,
            "langfuse": langfuse,
            "langfuse_host": get_settings().langfuse_host,
            "active_page": "stats",
        },
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


# --- LiveKit management ---


def _get_livekit_api():
    """Create a LiveKit API client from settings."""
    settings = get_settings()
    if not settings.livekit_url or not settings.livekit_api_key:
        return None, settings
    lkapi = api.LiveKitAPI(
        url=settings.livekit_url.replace("wss://", "https://"),
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    return lkapi, settings


def _parse_persona(room_name: str) -> str:
    """Extract persona from room name like 'talker-receptionist-abc123'."""
    parts = room_name.split("-")
    if len(parts) >= 3 and parts[0] == "talker":
        return "-".join(parts[1:-1])
    return "unknown"


def _format_duration(created_at_ns: int) -> str:
    """Format room duration from creation timestamp (nanoseconds)."""
    if not created_at_ns:
        return "—"
    elapsed = time.time() - (created_at_ns / 1e9)
    if elapsed < 60:
        return f"{int(elapsed)}s"
    if elapsed < 3600:
        return f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
    return f"{int(elapsed // 3600)}h {int((elapsed % 3600) // 60)}m"


@router.get("/livekit", dependencies=[Depends(verify_admin)])
async def admin_livekit(request: Request):
    lkapi, settings = _get_livekit_api()

    status = {
        "connected": lkapi is not None,
        "url": settings.livekit_url or "",
        "agent": None,
    }
    rooms = []

    if lkapi:
        try:
            resp = await lkapi.room.list_rooms(api.ListRoomsRequest())
            rooms = [
                {
                    "name": r.name,
                    "persona": _parse_persona(r.name),
                    "num_participants": r.num_participants,
                    "duration": _format_duration(r.creation_time),
                }
                for r in resp.rooms
            ]
        except Exception as e:
            log.warning("Failed to list LiveKit rooms: %s", e)
        finally:
            await lkapi.aclose()

    return templates.TemplateResponse(
        request=request,
        name="admin/livekit.html",
        context={
            "status": status,
            "rooms": rooms,
            "active_page": "livekit",
            "livekit_dashboard": "https://cloud.livekit.io",
            "message": request.query_params.get("message"),
        },
    )


@router.post("/livekit/close-room", dependencies=[Depends(verify_admin)])
async def admin_close_room(request: Request, room_name: str = Form()):
    lkapi, _ = _get_livekit_api()
    if not lkapi:
        return RedirectResponse(
            url="/admin/livekit?message=LiveKit+not+configured", status_code=303
        )

    try:
        await lkapi.room.delete_room(api.DeleteRoomRequest(room=room_name))
        msg = f"Closed+room+{room_name}"
    except Exception as e:
        msg = f"Error:+{str(e)[:100]}"
    finally:
        await lkapi.aclose()

    return RedirectResponse(url=f"/admin/livekit?message={msg}", status_code=303)
