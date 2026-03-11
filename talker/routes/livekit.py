"""LiveKit integration routes — token generation and voice session page."""

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from livekit import api

from talker.config import get_settings
from talker.services.tracing import create_trace, create_score

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
    user_id = request.session.get("user_id")
    user_email = request.session.get("user_email")
    user_name = request.session.get("user_name")
    if persona in _AUTH_REQUIRED_PERSONAS:
        if not user_id:
            return JSONResponse(
                {"error": "Authentication required for this persona"},
                status_code=401,
            )
        participant_name = user_name or participant_name

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

    # Create the room and dispatch the agent explicitly
    lkapi = api.LiveKitAPI(
        url=settings.livekit_url.replace("wss://", "https://"),
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    try:
        await lkapi.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=300))
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(room=room_name, agent_name="talker")
        )
    finally:
        await lkapi.aclose()

    # Create Langfuse trace for this voice session
    trace = create_trace(
        session_id=room_name,
        agent_name=persona,
        user_id=str(user_id) if user_id else participant_id,
        user_email=user_email,
        user_name=user_name or participant_name,
    )
    trace_id = trace.id if trace else None

    log.info("LiveKit token generated: room=%s persona=%s", room_name, persona)

    return JSONResponse({
        "token": token,
        "room": room_name,
        "livekit_url": settings.livekit_url,
        "participant_id": participant_id,
        "trace_id": trace_id,
    })


@router.post("/api/feedback")
async def submit_feedback(request: Request):
    """Receive user feedback score and send to Langfuse."""
    body = await request.json()
    trace_id = body.get("trace_id")
    rating = body.get("rating")  # 1-5
    comment = body.get("comment", "")

    if not trace_id or rating is None:
        return JSONResponse({"error": "trace_id and rating required"}, status_code=400)

    # Normalize 1-5 star rating to 0-1 for Langfuse
    normalized = (float(rating) - 1) / 4.0

    create_score(
        trace_id=trace_id,
        name="user-feedback",
        value=normalized,
        comment=comment or f"{rating}/5 stars",
    )

    return JSONResponse({"ok": True})
