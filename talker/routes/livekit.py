"""LiveKit integration routes — token generation and voice session page."""

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from livekit import api

from talker.config import get_settings

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()
log = logging.getLogger(__name__)

# Personas that require a logged-in user
_AUTH_REQUIRED_PERSONAS = {"assessor", "assessor-basic"}


@router.get("/livekit/voice")
async def livekit_voice_page(request: Request, persona: str = "receptionist"):
    """Serve the LiveKit voice session UI."""
    settings = get_settings()
    if not settings.livekit_url:
        return templates.TemplateResponse(
            request=request,
            name="error_generic.html",
            context={"message": "LiveKit is not configured. Set LIVEKIT_URL in your environment."},
            status_code=503,
        )

    # Assessor requires authentication
    if persona in _AUTH_REQUIRED_PERSONAS:
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="livekit_voice.html",
        context={
            "persona": persona,
            "livekit_url": settings.livekit_url,
        },
    )


@router.post("/api/livekit/token")
async def create_livekit_token(request: Request):
    """Generate a LiveKit access token for a participant to join a room."""
    settings = get_settings()
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        return JSONResponse(
            {"error": "LiveKit credentials not configured"},
            status_code=503,
        )

    body = await request.json()
    persona = body.get("persona", "receptionist")
    participant_name = body.get("name", "User")

    # Assessor requires authentication
    if persona in _AUTH_REQUIRED_PERSONAS:
        user_id = request.session.get("user_id")
        if not user_id:
            return JSONResponse(
                {"error": "Authentication required for this persona"},
                status_code=401,
            )
        # Use real user name if available
        participant_name = request.session.get("user_name", participant_name)

    room_name = f"talker-{persona}-{uuid.uuid4().hex[:8]}"
    participant_id = f"user-{uuid.uuid4().hex[:8]}"

    token = (
        api.AccessToken(
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
        .with_identity(participant_id)
        .with_name(participant_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )

    log.info("LiveKit token generated: room=%s persona=%s", room_name, persona)

    return JSONResponse({
        "token": token,
        "room": room_name,
        "livekit_url": settings.livekit_url,
        "participant_id": participant_id,
    })
