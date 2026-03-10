from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from talker.agents.orchestrator import Orchestrator
from talker.services.instruments import InstrumentLoader

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/assess")

# In-memory session store for MVP. Replace with DB-backed sessions later.
_sessions: dict[str, Orchestrator] = {}
_session_counter = 0
_chat_histories: dict[str, list[dict]] = {}


def _new_session_id() -> str:
    global _session_counter
    _session_counter += 1
    return str(_session_counter)


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
):
    session_id = _new_session_id()
    orch = Orchestrator()
    orch.start()

    if full_checkup:
        orch.select_full_checkup()
    elif instruments:
        orch.select_instruments(instruments)
    else:
        orch.select_full_checkup()

    _sessions[session_id] = orch
    return RedirectResponse(url=f"/assess/screening?session_id={session_id}", status_code=303)


@router.get("/screening")
async def assess_screening(request: Request, session_id: str):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    question_data = orch.get_current_screening_question()
    if not question_data:
        return RedirectResponse(url=f"/assess/conversation?session_id={session_id}")

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
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    result = orch.submit_screening_answer(value)

    if result["action"] == "screening_complete":
        return RedirectResponse(url=f"/assess/conversation?session_id={session_id}", status_code=303)

    return RedirectResponse(url=f"/assess/screening?session_id={session_id}", status_code=303)


@router.get("/conversation")
async def assess_conversation(request: Request, session_id: str):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    messages = _chat_histories.get(session_id, [])
    if not messages:
        ctx = orch.get_conversation_context()
        intro = "Thank you for completing the screenings. I'd like to learn more about how you've been feeling. "
        if orch.completed_results:
            intro += "Based on your responses, I have a few areas I'd like to explore with you. How are you doing right now?"
        messages = [{"role": "assistant", "content": intro}]
        _chat_histories[session_id] = messages

    return templates.TemplateResponse(
        request=request,
        name="assess_conversation.html",
        context={"session_id": session_id, "messages": messages},
    )


@router.post("/chat")
async def assess_chat(
    request: Request,
    session_id: str = Form(),
    message: str = Form(),
):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    messages = _chat_histories.get(session_id, [])
    messages.append({"role": "user", "content": message})

    # Safety check
    safety_result = orch.check_safety(message)
    if safety_result:
        safety_msg = safety_result.message + "\n\n" + "\n".join(f"- {r}" for r in safety_result.resources)
        messages.append({"role": "assistant", "content": safety_msg})
        _chat_histories[session_id] = messages
        return RedirectResponse(url=f"/assess/conversation?session_id={session_id}", status_code=303)

    # TODO: Integrate LLM call here. For now, static response.
    messages.append({
        "role": "assistant",
        "content": "Thank you for sharing that. Could you tell me more about how this has been affecting your daily life?",
    })
    _chat_histories[session_id] = messages

    return RedirectResponse(url=f"/assess/conversation?session_id={session_id}", status_code=303)


@router.get("/summary")
async def assess_summary(request: Request, session_id: str):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    orch.skip_follow_up()
    results = orch.completed_results

    recommendations = []
    for r in results:
        if r.severity in ("moderate", "moderately severe", "severe", "above threshold"):
            recommendations.append(
                f"Your {r.instrument_id.upper()} score ({r.score}) suggests {r.severity} symptoms. "
                f"Consider consulting a mental health professional about this area."
            )
        if r.flagged_items:
            recommendations.append(
                f"Some responses on {r.instrument_id.upper()} were flagged for follow-up."
            )

    if not recommendations:
        recommendations.append(
            "Your screening scores are in the minimal/mild range. "
            "If you're still concerned, a professional consultation can provide more clarity."
        )

    orch.complete()

    return templates.TemplateResponse(
        request=request,
        name="assess_summary.html",
        context={
            "session_id": session_id,
            "results": results,
            "recommendations": recommendations,
        },
    )
