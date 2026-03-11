import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.agents.orchestrator import Orchestrator
from talker.config import get_settings
from talker.models.schemas import SessionState
from talker.services.instruments import InstrumentLoader
from talker.services.session_repo import SessionRepository

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/assess")


@router.get("")
async def assess_start(request: Request):
    loader = InstrumentLoader("talker/instruments")
    instruments = loader.load_all()
    metas = [i.metadata for i in instruments]
    return templates.TemplateResponse(
        request=request,
        name="assess.html",
        context={"instruments": metas},
    )


@router.post("/start")
async def assess_begin(
    request: Request,
    instruments: list[str] = Form(default=[]),
    full_checkup: str = Form(default=""),
    voice: str = Form(default=""),
):
    orch = Orchestrator()

    if full_checkup:
        instrument_queue = orch.get_all_instrument_ids()
    elif instruments:
        instrument_queue = instruments
    else:
        instrument_queue = orch.get_all_instrument_ids()

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session_id = await repo.create(instrument_queue=instrument_queue)
        await db.commit()

    if voice:
        return RedirectResponse(
            url=f"/assess/voice?session_id={session_id}", status_code=303
        )

    return RedirectResponse(
        url=f"/assess/screening?session_id={session_id}", status_code=303
    )


@router.get("/screening")
async def assess_screening(request: Request, session_id: str):
    sid = uuid.UUID(session_id)
    orch = Orchestrator()

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)

    if not session:
        return RedirectResponse(url="/assess")

    question_data = orch.get_current_screening_question(session)
    if not question_data:
        return RedirectResponse(
            url=f"/assess/conversation?session_id={session_id}"
        )

    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load(question_data["instrument_id"])

    return templates.TemplateResponse(
        request=request,
        name="assess_screening.html",
        context={
            "session_id": session_id,
            "instrument_name": instrument.metadata.name,
            "question_text": question_data["question"],
            "question_number": question_data["question_number"],
            "total_questions": question_data["total_questions"],
            "response_options": question_data["response_options"],
        },
    )


@router.post("/answer")
async def assess_answer(
    request: Request,
    session_id: str = Form(),
    value: int = Form(),
):
    sid = uuid.UUID(session_id)
    orch = Orchestrator()

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)
        if not session:
            return RedirectResponse(url="/assess")

        # Save the answer for current question
        question_data = orch.get_current_screening_question(session)
        if question_data:
            screener = orch._build_screener(session)
            q = screener.get_current_question()
            if q:
                await repo.save_answer(sid, q.id, value)

        # Reload to get updated answers, then process
        session = await repo.load(sid)
        result = orch.submit_screening_answer(session, value)

        if result["result"]:
            await repo.save_screening(sid, result["result"])
            await repo.clear_current_answers(sid)

        if result["action"] == "screening_complete":
            await repo.update_state(
                sid, SessionState.FOLLOW_UP, result["next_index"]
            )
            await db.commit()
            return RedirectResponse(
                url=f"/assess/conversation?session_id={session_id}",
                status_code=303,
            )
        elif result["action"] == "next_instrument":
            await repo.update_state(
                sid, SessionState.SCREENING, result["next_index"]
            )

        await db.commit()

    return RedirectResponse(
        url=f"/assess/screening?session_id={session_id}", status_code=303
    )


@router.get("/conversation")
async def assess_conversation(request: Request, session_id: str):
    sid = uuid.UUID(session_id)

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)
        if not session:
            return RedirectResponse(url="/assess")

        messages = [
            {"role": m.role, "content": m.content} for m in session.chat_messages
        ]
        if not messages:
            intro = (
                "Thank you for completing the screenings. "
                "I'd like to learn more about how you've been feeling. "
            )
            if session.completed_results:
                intro += (
                    "Based on your responses, I have a few areas I'd like "
                    "to explore with you. How are you doing right now?"
                )
            messages = [{"role": "assistant", "content": intro}]
            await repo.save_message(sid, "assistant", intro)
            await db.commit()

    return templates.TemplateResponse(
        request=request,
        name="assess_conversation.html",
        context={"session_id": session_id, "messages": messages},
    )


async def _get_llm_response(
    orch: Orchestrator, session, messages: list[dict], user_message: str
) -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        return (
            "Thank you for sharing that. Could you tell me more about "
            "how this has been affecting your daily life?"
        )

    ctx = orch.get_conversation_context(session)
    system_prompt = orch.conversation.build_system_prompt(ctx)

    model = OpenAIChatModel(
        settings.openrouter_model_conversation,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    )
    agent = Agent(model, system_prompt=system_prompt)

    history_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages[-10:]
    )

    result = await agent.run(
        f"Conversation so far:\n{history_text}\n\nUser: {user_message}"
    )
    return result.output


@router.post("/chat")
async def assess_chat(
    request: Request,
    session_id: str = Form(),
    message: str = Form(),
):
    sid = uuid.UUID(session_id)
    orch = Orchestrator()

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)
        if not session:
            return RedirectResponse(url="/assess")

        await repo.save_message(sid, "user", message)

        # Safety check
        safety_result = orch.check_safety(message)
        if safety_result:
            safety_msg = (
                safety_result.message
                + "\n\n"
                + "\n".join(f"- {r}" for r in safety_result.resources)
            )
            await repo.save_message(sid, "assistant", safety_msg)
            await repo.save_safety_event(
                sid,
                trigger=safety_result.trigger,
                agent="conversation",
                message_shown=safety_msg,
                resources=safety_result.resources,
            )
            await db.commit()
            return RedirectResponse(
                url=f"/assess/conversation?session_id={session_id}",
                status_code=303,
            )

        messages = [
            {"role": m.role, "content": m.content} for m in session.chat_messages
        ]
        messages.append({"role": "user", "content": message})

        response = await _get_llm_response(orch, session, messages, message)
        await repo.save_message(sid, "assistant", response)
        await db.commit()

    return RedirectResponse(
        url=f"/assess/conversation?session_id={session_id}", status_code=303
    )


@router.get("/summary")
async def assess_summary(request: Request, session_id: str):
    sid = uuid.UUID(session_id)

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)
        if not session:
            return RedirectResponse(url="/assess")

        results = session.completed_results
        recommendations = []
        for r in results:
            if r.severity in (
                "moderate",
                "moderately severe",
                "severe",
                "above threshold",
            ):
                recommendations.append(
                    f"Your {r.instrument_id.upper()} score ({r.score}) suggests "
                    f"{r.severity} symptoms. Consider consulting a mental health "
                    f"professional about this area."
                )
            if r.flagged_items:
                recommendations.append(
                    f"Some responses on {r.instrument_id.upper()} were flagged "
                    f"for follow-up."
                )

        if not recommendations:
            recommendations.append(
                "Your screening scores are in the minimal/mild range. "
                "If you're still concerned, a professional consultation "
                "can provide more clarity."
            )

        await repo.save_summary(
            sid,
            instruments_completed=[r.instrument_id for r in results],
            recommendations=recommendations,
        )
        await repo.update_state(sid, SessionState.COMPLETED)
        await db.commit()

    return templates.TemplateResponse(
        request=request,
        name="assess_summary.html",
        context={
            "session_id": session_id,
            "results": results,
            "recommendations": recommendations,
        },
    )
