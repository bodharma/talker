"""Psychology assessor persona — DSM-5 screening via voice with LLM follow-up.

Wraps the existing orchestrator/screener/conversation/safety stack as a
LiveKit persona with @function_tool functions. The same clinical logic,
different transport.

State is held in a module-level SessionData object per conversation,
since LiveKit sessions are 1:1 agent-to-room.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from livekit.agents import Agent, RunContext, function_tool

from talker.agents.orchestrator import Orchestrator
from talker.models.schemas import SessionData, SessionState

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-session state (one session per LiveKit room)
# ---------------------------------------------------------------------------

_session: SessionData | None = None
_orchestrator = Orchestrator()


def _ensure_session() -> SessionData:
    """Get or create the current session."""
    global _session
    if _session is None:
        _session = SessionData(
            id=uuid.uuid4(),
            state=SessionState.CREATED,
            created_at=datetime.now(timezone.utc),
        )
    return _session


def _reset_session() -> None:
    """Reset for a new conversation."""
    global _session
    _session = None


# ---------------------------------------------------------------------------
# Tools — triage
# ---------------------------------------------------------------------------

@function_tool()
async def list_available_instruments(
    context: RunContext,
) -> dict[str, Any]:
    """List all available psychological screening instruments with their descriptions.
    Call this to know what assessments are available before starting."""
    ids = _orchestrator.get_all_instrument_ids()
    instruments = []
    for iid in ids:
        defn = _orchestrator.loader.load(iid)
        instruments.append({
            "id": iid,
            "name": defn.metadata.name,
            "description": defn.metadata.description,
            "question_count": len(defn.questions),
        })
    return {"instruments": instruments, "count": len(instruments)}


@function_tool()
async def triage_symptoms(
    context: RunContext,
    user_description: str,
) -> dict[str, Any]:
    """Based on the user's description of their symptoms, determine which screening
    instruments are most appropriate. Returns a triage prompt for the LLM to decide.

    Args:
        user_description: What the user told you about how they're feeling.
    """
    prompt = _orchestrator.get_triage_prompt(user_description)
    return {
        "triage_prompt": prompt,
        "available_instruments": _orchestrator.get_all_instrument_ids(),
    }


@function_tool()
async def start_assessment(
    context: RunContext,
    instrument_ids: list[str],
) -> dict[str, Any]:
    """Start a screening assessment with the selected instruments.
    Call this after triage to begin asking questions.

    Args:
        instrument_ids: List of instrument IDs to administer (e.g. ["phq-9", "gad-7"]).
    """
    session = _ensure_session()
    valid = _orchestrator.parse_triage_result(instrument_ids)

    if not valid:
        return {"started": False, "error": "No valid instruments selected."}

    session.instrument_queue = valid
    session.current_instrument_index = 0
    session.state = SessionState.SCREENING

    question = _orchestrator.get_current_screening_question(session)
    return {
        "started": True,
        "instruments": valid,
        "total_instruments": len(valid),
        "first_question": question,
    }


# ---------------------------------------------------------------------------
# Tools — screening
# ---------------------------------------------------------------------------

@function_tool()
async def get_current_question(
    context: RunContext,
) -> dict[str, Any]:
    """Get the current screening question to ask the user.
    Returns the question text, response options, and progress."""
    session = _ensure_session()
    question = _orchestrator.get_current_screening_question(session)

    if question is None:
        return {"has_question": False, "screening_complete": True}

    return {"has_question": True, **question}


@function_tool()
async def submit_answer(
    context: RunContext,
    value: int,
) -> dict[str, Any]:
    """Submit the user's answer to the current screening question.
    The value must match one of the response option values (typically 0-3).

    Args:
        value: The numeric score for the user's answer (e.g. 0=Not at all, 3=Nearly every day).
    """
    session = _ensure_session()
    result = _orchestrator.submit_screening_answer(session, value)
    return result


@function_tool()
async def check_safety(
    context: RunContext,
    user_text: str,
) -> dict[str, Any]:
    """Check user text for crisis indicators. MUST be called on every user message.
    If a safety event is detected, immediately provide crisis resources.

    Args:
        user_text: The user's message to check for crisis language.
    """
    event = _orchestrator.check_safety(user_text)
    if event is None:
        return {"safe": True}

    session = _ensure_session()
    session.state = SessionState.INTERRUPTED_BY_SAFETY

    return {
        "safe": False,
        "trigger": event.trigger,
        "message": event.message,
        "resources": event.resources,
        "action": "STOP assessment immediately. Provide these crisis resources.",
    }


# ---------------------------------------------------------------------------
# Tools — conversation follow-up
# ---------------------------------------------------------------------------

@function_tool()
async def start_followup_conversation(
    context: RunContext,
) -> dict[str, Any]:
    """Start the follow-up conversation phase after all screening instruments are done.
    Returns a system prompt with screening results for the LLM to guide the conversation."""
    session = _ensure_session()
    session.state = SessionState.FOLLOW_UP

    conv_context = _orchestrator.get_conversation_context(session)
    prompt = _orchestrator.conversation.build_system_prompt(conv_context)

    return {
        "phase": "follow_up",
        "system_prompt": prompt,
        "completed_instruments": len(session.completed_results),
        "results_summary": [
            {
                "instrument": r.instrument_id,
                "score": r.score,
                "severity": r.severity,
                "flagged_items": r.flagged_items,
            }
            for r in session.completed_results
        ],
    }


@function_tool()
async def get_score_interpretation(
    context: RunContext,
    instrument_id: str,
    score: int,
) -> dict[str, Any]:
    """Get a human-readable interpretation of a screening score.

    Args:
        instrument_id: The instrument (e.g. "phq-9").
        score: The total score to interpret.
    """
    interpretation = _orchestrator.get_score_context_for_result(instrument_id, score)
    return {"instrument_id": instrument_id, "score": score, "interpretation": interpretation}


@function_tool()
async def get_assessment_summary(
    context: RunContext,
) -> dict[str, Any]:
    """Get a complete summary of all screening results and recommendations.
    Call this at the end of the conversation to wrap up."""
    session = _ensure_session()
    session.state = SessionState.SUMMARY

    results = []
    for r in session.completed_results:
        interp = _orchestrator.get_score_context_for_result(r.instrument_id, r.score)
        results.append({
            "instrument": r.instrument_id,
            "score": r.score,
            "severity": r.severity,
            "flagged_items": r.flagged_items,
            "interpretation": interp,
        })

    return {
        "session_id": session.id,
        "total_instruments": len(results),
        "results": results,
        "reminder": "This is a screening tool, not a diagnosis. Recommend professional follow-up.",
    }


# ---------------------------------------------------------------------------
# Assessor Agent
# ---------------------------------------------------------------------------

ASSESSOR_INSTRUCTIONS = """\
You are a psychology pre-assessment assistant. You guide people through validated \
DSM-5 screening questionnaires and have a supportive follow-up conversation about their results.

You are NOT a therapist, NOT a doctor, and you CANNOT diagnose. You are a guide that helps \
people understand their symptoms and know where to seek professional help. Make this clear \
at the start.

Your flow:
1. Greet warmly. Explain what you do and what you don't do (disclaimers)
2. Ask how they're feeling in their own words
3. Use triage_symptoms to determine which instruments are appropriate
4. Use start_assessment to begin the screening
5. For each question: use get_current_question, read it EXACTLY as written (clinical validity \
   depends on exact wording), present the response options, then use submit_answer with their choice
6. When screening is complete, use start_followup_conversation to get the context
7. Have a brief, supportive conversation exploring flagged areas
8. Use get_assessment_summary to wrap up with recommendations

CRITICAL RULES:
- Call check_safety on EVERY user message. If it returns unsafe, STOP everything and provide \
  crisis resources immediately. This is non-negotiable.
- Read screening questions EXACTLY as written. Do not rephrase, simplify, or add commentary. \
  Clinical validity depends on standardized wording.
- When presenting response options, read all of them. Let the user choose.
- One question at a time. Never batch questions.
- After screening, the conversation should be warm and exploratory, not clinical. \
  Ask about their experience, validate their feelings, suggest next steps.

Style:
- Warm, calm, and professional. This is a sensitive topic.
- Keep responses concise — especially during screening (just the question + options).
- During follow-up, be more conversational but still brief (2-3 sentences + a question).
- Never minimize their experience. Never say "just" or "only" about their scores.
- Use plain language, not clinical jargon.
"""


class AssessorAgent(Agent):
    """Psychology pre-assessment agent — screening + follow-up via voice."""

    def __init__(self) -> None:
        super().__init__(
            instructions=ASSESSOR_INSTRUCTIONS,
            tools=[
                list_available_instruments,
                triage_symptoms,
                start_assessment,
                get_current_question,
                submit_answer,
                check_safety,
                start_followup_conversation,
                get_score_interpretation,
                get_assessment_summary,
            ],
        )
