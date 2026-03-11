import logging

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from talker.config import get_settings
from talker.services.instruments import InstrumentLoader
from talker.services.voice import CloudVoiceProvider, LocalVoiceProvider, VoiceProviderError

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/settings")
async def settings_page(request: Request):
    settings = get_settings()
    loader = InstrumentLoader("talker/instruments")
    instruments = [i.metadata for i in loader.load_all()]

    # Voice models
    if settings.voice_provider == "cloud" and settings.deepgram_api_key:
        stt_models = CloudVoiceProvider.available_stt_models()
        tts_models: list[dict] = []
        try:
            cloud = CloudVoiceProvider(
                deepgram_api_key=settings.deepgram_api_key,
                elevenlabs_api_key=settings.elevenlabs_api_key,
                deepgram_model=settings.deepgram_model,
                elevenlabs_model=settings.elevenlabs_model,
                elevenlabs_voice_id=settings.elevenlabs_voice_id,
            )
            tts_models = [
                {"id": v["voice_id"], "name": v["name"]}
                for v in cloud.available_tts_voices()
            ]
        except VoiceProviderError:
            log.warning("Failed to initialize cloud voice provider for settings")
        current_stt = settings.deepgram_model
        current_tts = settings.elevenlabs_voice_id
    else:
        stt_models = LocalVoiceProvider.available_stt_models()
        local_tts = LocalVoiceProvider.available_tts_models(
            settings.voice_local_models_dir
        )
        tts_models = [{"id": m, "name": m} for m in local_tts]
        current_stt = settings.voice_local_stt_model
        current_tts = settings.voice_local_tts_model

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "openrouter_configured": bool(settings.openrouter_api_key),
            "langfuse_configured": bool(settings.langfuse_secret_key),
            "db_connected": True,
            "conversation_model": settings.openrouter_model_conversation,
            "screener_model": settings.openrouter_model_screener,
            "instruments": instruments,
            "voice_provider": settings.voice_provider,
            "cloud_voice_available": bool(
                settings.deepgram_api_key and settings.elevenlabs_api_key
            ),
            "stt_models": stt_models,
            "tts_models": tts_models,
            "current_stt_model": current_stt,
            "current_tts_model": current_tts,
            "deepgram_configured": bool(settings.deepgram_api_key),
            "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        },
    )
