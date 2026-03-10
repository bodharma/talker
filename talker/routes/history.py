from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/history")


@router.get("")
async def history_list(request: Request):
    # TODO: Query from database. For now, empty list.
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"sessions": []},
    )


@router.get("/{session_id}")
async def history_detail(request: Request, session_id: int):
    # TODO: Query from database.
    return RedirectResponse(url="/history")
