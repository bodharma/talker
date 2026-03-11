import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from talker.routes.deps import verify_auth
from talker.services.session_repo import SessionRepository
from talker.services.trends import TrendService

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/history")


@router.get("")
async def history_list(request: Request, user_id: int = Depends(verify_auth)):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        sessions = await repo.list_completed(user_id=user_id)

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"sessions": sessions},
    )


@router.get("/trends")
async def history_trends(request: Request, user_id: int = Depends(verify_auth)):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        svc = TrendService(db)
        summary = await svc.get_trend_summary(user_id)
        chart_data = await svc.get_chart_data(user_id)

    return templates.TemplateResponse(
        request=request,
        name="trends.html",
        context={
            "summary": summary,
            "chart_data_json": json.dumps(chart_data),
        },
    )


@router.get("/{session_id}")
async def history_detail(request: Request, session_id: str):
    sid = uuid.UUID(session_id)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.get_detail(sid)

    if not session:
        return RedirectResponse(url="/history")

    return templates.TemplateResponse(
        request=request,
        name="session_detail.html",
        context={"session": session},
    )
