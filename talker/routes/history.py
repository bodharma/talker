import uuid

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from talker.services.session_repo import SessionRepository

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/history")


@router.get("")
async def history_list(request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        sessions = await repo.list_completed()

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"sessions": sessions},
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
