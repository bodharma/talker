import base64
import json
import logging
import uuid

import numpy as np
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from talker.agents.orchestrator import Orchestrator
from talker.agents.voice_mapper import map_voice_answer
from talker.config import get_settings
from talker.models.schemas import SessionState
from talker.services.instruments import InstrumentLoader
from talker.services.session_repo import SessionRepository
from talker.services.voice import (
    CloudVoiceProvider,
    LocalVoiceProvider,
    VoiceProviderError,
    create_voice_provider,
)
from talker.services.voice_features import extract_features

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/assess/voice")
async def assess_voice_page(request: Request, session_id: str):
    """Serve the dedicated voice assessment UI."""
    sid = uuid.UUID(session_id)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)
        if not session:
            return templates.TemplateResponse(request=request, name="index.html")

    return templates.TemplateResponse(
        request=request,
        name="assess_voice.html",
        context={"session_id": session_id},
    )


@router.websocket("/ws/voice/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for voice I/O."""
    await websocket.accept()
    sid = uuid.UUID(session_id)
    settings = get_settings()

    try:
        provider = create_voice_provider(settings)
    except VoiceProviderError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
        return

    session_factory = websocket.app.state.db_session_factory
    orch = Orchestrator()
    loader = InstrumentLoader("talker/instruments")
    audio_buffer: list[np.ndarray] = []
    utterance_index = 0

    try:
        # Load session and send initial state
        async with session_factory() as db:
            repo = SessionRepository(db)
            session = await repo.load(sid)
            if not session:
                await websocket.send_json(
                    {"type": "error", "message": "Session not found"}
                )
                await websocket.close()
                return

        await _send_current_state(websocket, orch, session, loader, provider)

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "audio":
                audio_bytes = base64.b64decode(msg["data"])
                audio_chunk = (
                    np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                    / 32767.0
                )
                audio_buffer.append(audio_chunk)

            elif msg_type == "stop":
                if not audio_buffer:
                    continue

                full_audio = np.concatenate(audio_buffer)
                audio_buffer.clear()

                await websocket.send_json({"type": "listening", "active": False})
                transcript = await provider.transcribe(full_audio)
                if not transcript.strip():
                    await websocket.send_json({"type": "listening", "active": True})
                    continue

                await websocket.send_json(
                    {"type": "transcript", "text": transcript, "final": True}
                )

                # Extract and store voice features
                features = extract_features(
                    full_audio, sample_rate=16000, transcript=transcript
                )
                async with session_factory() as db:
                    repo = SessionRepository(db)
                    await repo.save_voice_features(
                        sid, utterance_index, "user", features
                    )
                    await db.commit()
                utterance_index += 1

                # Reload session
                async with session_factory() as db:
                    repo = SessionRepository(db)
                    session = await repo.load(sid)

                # Safety check first
                safety_result = orch.check_safety(transcript)
                if safety_result:
                    safety_msg = (
                        safety_result.message
                        + " "
                        + " ".join(safety_result.resources)
                    )
                    async with session_factory() as db:
                        repo = SessionRepository(db)
                        await repo.save_message(sid, "user", transcript)
                        await repo.save_message(sid, "assistant", safety_msg)
                        await repo.save_safety_event(
                            sid,
                            trigger=safety_result.trigger,
                            agent="voice",
                            message_shown=safety_msg,
                            resources=safety_result.resources,
                        )
                        await db.commit()
                    tts_audio, _ = await provider.synthesize(safety_msg)
                    audio_b64 = base64.b64encode(tts_audio).decode()
                    await websocket.send_json(
                        {
                            "type": "safety",
                            "message": safety_msg,
                            "resources": safety_result.resources,
                            "audio": audio_b64,
                        }
                    )
                    await websocket.send_json({"type": "listening", "active": True})
                    continue

                # Process based on session state
                response_text = await _process_voice_input(
                    orch, session, transcript, sid, session_factory, loader
                )

                if response_text:
                    tts_audio, _ = await provider.synthesize(response_text)
                    audio_b64 = base64.b64encode(tts_audio).decode()
                    await websocket.send_json(
                        {
                            "type": "response",
                            "text": response_text,
                            "audio": audio_b64,
                        }
                    )

                # Send updated state
                async with session_factory() as db:
                    repo = SessionRepository(db)
                    session = await repo.load(sid)
                await _send_current_state(websocket, orch, session, loader, None)
                await websocket.send_json({"type": "listening", "active": True})

            elif msg_type == "start":
                audio_buffer.clear()
                await websocket.send_json({"type": "listening", "active": True})

            elif msg_type == "interrupt":
                audio_buffer.clear()

    except WebSocketDisconnect:
        log.info("Voice WebSocket disconnected: session %s", session_id)


async def _send_current_state(websocket, orch, session, loader, provider):
    """Send the current session state and speak the current prompt if provider given."""
    if session.state == SessionState.SCREENING:
        question_data = orch.get_current_screening_question(session)
        if question_data:
            instrument = loader.load(question_data["instrument_id"])
            await websocket.send_json(
                {
                    "type": "state",
                    "state": "screening",
                    "instrument": instrument.metadata.name,
                    "question": question_data["question_number"],
                    "total": question_data["total_questions"],
                }
            )
            if provider:
                tts_audio, _ = await provider.synthesize(question_data["question"])
                audio_b64 = base64.b64encode(tts_audio).decode()
                await websocket.send_json(
                    {
                        "type": "response",
                        "text": question_data["question"],
                        "audio": audio_b64,
                    }
                )
        else:
            await websocket.send_json({"type": "state", "state": "conversation"})
    elif session.state == SessionState.FOLLOW_UP:
        await websocket.send_json({"type": "state", "state": "conversation"})
    elif session.state == SessionState.COMPLETED:
        await websocket.send_json({"type": "state", "state": "completed"})


async def _process_voice_input(orch, session, transcript, sid, session_factory, loader):
    """Process a voice transcript based on current session state."""
    from talker.routes.assess import _get_llm_response

    if session.state == SessionState.SCREENING:
        question_data = orch.get_current_screening_question(session)
        if not question_data:
            return None

        options = [
            {"value": opt["value"], "text": opt["text"]}
            for opt in question_data["response_options"]
        ]

        mapping = await map_voice_answer(
            question=question_data["question"],
            options=options,
            transcript=transcript,
        )

        if mapping.confidence < 0.7:
            closest = next(
                (opt["text"] for opt in options if opt["value"] == mapping.value),
                "that option",
            )
            return f'Just to make sure I understand — did you mean "{closest}"?'

        async with session_factory() as db:
            repo = SessionRepository(db)
            screener = orch._build_screener(session)
            q = screener.get_current_question()
            if q:
                await repo.save_answer(sid, q.id, mapping.value)

            session = await repo.load(sid)
            result = orch.submit_screening_answer(session, mapping.value)

            if result["result"]:
                await repo.save_screening(sid, result["result"])
                await repo.clear_current_answers(sid)

            if result["action"] == "screening_complete":
                await repo.update_state(
                    sid, SessionState.FOLLOW_UP, result["next_index"]
                )
                intro = (
                    "Thank you for completing the screenings. "
                    "I'd like to learn more about how you've been feeling. "
                    "How are you doing right now?"
                )
                await repo.save_message(sid, "assistant", intro)
                await db.commit()
                return intro
            elif result["action"] == "next_instrument":
                await repo.update_state(
                    sid, SessionState.SCREENING, result["next_index"]
                )

            await db.commit()

        # Return next question
        async with session_factory() as db:
            repo = SessionRepository(db)
            session = await repo.load(sid)
        next_q = orch.get_current_screening_question(session)
        if next_q:
            return next_q["question"]
        return None

    elif session.state == SessionState.FOLLOW_UP:
        async with session_factory() as db:
            repo = SessionRepository(db)
            await repo.save_message(sid, "user", transcript)
            session = await repo.load(sid)
            messages = [
                {"role": m.role, "content": m.content} for m in session.chat_messages
            ]
            response = await _get_llm_response(orch, session, messages, transcript)
            await repo.save_message(sid, "assistant", response)
            await db.commit()
        return response

    return None


@router.get("/api/voice/models")
async def get_voice_models():
    """Return available voice models for the current provider."""
    settings = get_settings()

    if settings.voice_provider == "cloud":
        stt_models = CloudVoiceProvider.available_stt_models()
        tts_voices: list[dict] = []
        if settings.elevenlabs_api_key:
            try:
                cloud = CloudVoiceProvider(
                    deepgram_api_key=settings.deepgram_api_key,
                    elevenlabs_api_key=settings.elevenlabs_api_key,
                    deepgram_model=settings.deepgram_model,
                    elevenlabs_model=settings.elevenlabs_model,
                    elevenlabs_voice_id=settings.elevenlabs_voice_id,
                )
                tts_voices = cloud.available_tts_voices()
            except VoiceProviderError:
                pass
        return JSONResponse(
            {
                "provider": "cloud",
                "stt_models": stt_models,
                "tts_voices": tts_voices,
            }
        )
    else:
        return JSONResponse(
            {
                "provider": "local",
                "stt_models": LocalVoiceProvider.available_stt_models(),
                "tts_models": LocalVoiceProvider.available_tts_models(
                    settings.voice_local_models_dir
                ),
            }
        )
