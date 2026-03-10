from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from talker.config import get_settings
from talker.services.instruments import InstrumentLoader

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()


@router.get("/settings")
async def settings_page(request: Request):
    settings = get_settings()
    loader = InstrumentLoader("talker/instruments")
    instruments = [i.metadata for i in loader.load_all()]

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "openrouter_configured": bool(settings.openrouter_api_key),
            "langfuse_configured": bool(settings.langfuse_secret_key),
            "db_connected": True,  # TODO: actual health check
            "conversation_model": settings.openrouter_model_conversation,
            "screener_model": settings.openrouter_model_screener,
            "instruments": instruments,
        },
    )
