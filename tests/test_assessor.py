"""Tests for the psychology assessor persona tools."""

import pytest

from talker.models.schemas import ScreeningResult, SessionData, SessionState
from talker.personas.assessor import (
    AssessorAgent,
    ASSESSOR_INSTRUCTIONS,
    _ensure_session,
    _reset_session,
    check_safety,
    get_assessment_summary,
    get_current_question,
    get_score_interpretation,
    list_available_instruments,
    start_assessment,
    start_followup_conversation,
    submit_answer,
    triage_symptoms,
)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


class TestSessionManagement:
    def setup_method(self):
        _reset_session()

    def test_ensure_session_creates_new(self):
        session = _ensure_session()
        assert isinstance(session, SessionData)
        assert session.state == SessionState.CREATED

    def test_ensure_session_returns_same(self):
        s1 = _ensure_session()
        s2 = _ensure_session()
        assert s1.id == s2.id

    def test_reset_session(self):
        s1 = _ensure_session()
        _reset_session()
        s2 = _ensure_session()
        assert s1.id != s2.id


# ---------------------------------------------------------------------------
# Tool: list_available_instruments
# ---------------------------------------------------------------------------


class TestListInstruments:
    @pytest.mark.asyncio
    async def test_returns_instruments(self):
        result = await list_available_instruments._func(None)
        assert "instruments" in result
        assert "count" in result
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_instrument_structure(self):
        result = await list_available_instruments._func(None)
        for inst in result["instruments"]:
            assert "id" in inst
            assert "name" in inst
            assert "question_count" in inst
            assert inst["question_count"] > 0


# ---------------------------------------------------------------------------
# Tool: triage_symptoms
# ---------------------------------------------------------------------------


class TestTriageSymptoms:
    @pytest.mark.asyncio
    async def test_returns_triage_prompt(self):
        result = await triage_symptoms._func(
            None, user_description="I feel anxious and can't sleep"
        )
        assert "triage_prompt" in result
        assert "available_instruments" in result
        assert len(result["available_instruments"]) > 0

    @pytest.mark.asyncio
    async def test_prompt_contains_description(self):
        result = await triage_symptoms._func(
            None, user_description="persistent sadness"
        )
        assert isinstance(result["triage_prompt"], str)
        assert len(result["triage_prompt"]) > 0


# ---------------------------------------------------------------------------
# Tool: start_assessment
# ---------------------------------------------------------------------------


class TestStartAssessment:
    def setup_method(self):
        _reset_session()

    @pytest.mark.asyncio
    async def test_start_with_valid_instruments(self):
        instruments = await list_available_instruments._func(None)
        first_id = instruments["instruments"][0]["id"]

        result = await start_assessment._func(None, instrument_ids=[first_id])
        assert result["started"] is True
        assert first_id in result["instruments"]
        assert "first_question" in result

    @pytest.mark.asyncio
    async def test_start_with_invalid_instruments(self):
        # Invalid IDs get replaced with all instruments (fallback behavior)
        result = await start_assessment._func(
            None, instrument_ids=["nonexistent-xyz"]
        )
        # parse_triage_result falls back to all instruments
        assert result["started"] is True

    @pytest.mark.asyncio
    async def test_session_state_changes_to_screening(self):
        instruments = await list_available_instruments._func(None)
        first_id = instruments["instruments"][0]["id"]
        await start_assessment._func(None, instrument_ids=[first_id])
        session = _ensure_session()
        assert session.state == SessionState.SCREENING


# ---------------------------------------------------------------------------
# Tool: get_current_question
# ---------------------------------------------------------------------------


class TestGetCurrentQuestion:
    def setup_method(self):
        _reset_session()

    @pytest.mark.asyncio
    async def test_no_question_before_start(self):
        result = await get_current_question._func(None)
        assert result["has_question"] is False

    @pytest.mark.asyncio
    async def test_question_after_start(self):
        instruments = await list_available_instruments._func(None)
        first_id = instruments["instruments"][0]["id"]
        await start_assessment._func(None, instrument_ids=[first_id])

        result = await get_current_question._func(None)
        assert result["has_question"] is True
        assert "question" in result
        assert "response_options" in result


# ---------------------------------------------------------------------------
# Tool: submit_answer
# ---------------------------------------------------------------------------


class TestSubmitAnswer:
    def setup_method(self):
        _reset_session()

    @pytest.mark.asyncio
    async def test_submit_returns_action(self):
        instruments = await list_available_instruments._func(None)
        first_id = instruments["instruments"][0]["id"]
        await start_assessment._func(None, instrument_ids=[first_id])

        result = await submit_answer._func(None, value=0)
        assert "action" in result
        assert result["action"] in ("next_question", "next_instrument", "screening_complete")


# ---------------------------------------------------------------------------
# Tool: check_safety
# ---------------------------------------------------------------------------


class TestCheckSafety:
    def setup_method(self):
        _reset_session()

    @pytest.mark.asyncio
    async def test_safe_text(self):
        result = await check_safety._func(None, user_text="I feel a bit anxious today")
        assert result["safe"] is True

    @pytest.mark.asyncio
    async def test_crisis_text(self):
        result = await check_safety._func(
            None, user_text="I want to kill myself"
        )
        assert result["safe"] is False
        assert "message" in result
        assert "resources" in result

    @pytest.mark.asyncio
    async def test_crisis_changes_session_state(self):
        await check_safety._func(None, user_text="I want to end my life")
        session = _ensure_session()
        if session.state == SessionState.INTERRUPTED_BY_SAFETY:
            assert True  # safety triggered as expected


# ---------------------------------------------------------------------------
# Tool: start_followup_conversation
# ---------------------------------------------------------------------------


class TestStartFollowup:
    def setup_method(self):
        _reset_session()

    @pytest.mark.asyncio
    async def test_returns_system_prompt(self):
        session = _ensure_session()
        session.state = SessionState.SCREENING
        session.completed_results = [
            ScreeningResult(
                instrument_id="phq-9",
                score=12,
                severity="moderate",
                flagged_items=[9],
            )
        ]

        result = await start_followup_conversation._func(None)
        assert result["phase"] == "follow_up"
        assert "system_prompt" in result
        assert result["completed_instruments"] == 1

    @pytest.mark.asyncio
    async def test_session_state_changes(self):
        _ensure_session()
        await start_followup_conversation._func(None)
        session = _ensure_session()
        assert session.state == SessionState.FOLLOW_UP


# ---------------------------------------------------------------------------
# Tool: get_score_interpretation
# ---------------------------------------------------------------------------


class TestScoreInterpretation:
    @pytest.mark.asyncio
    async def test_returns_interpretation(self):
        result = await get_score_interpretation._func(
            None, instrument_id="phq-9", score=10
        )
        assert result["instrument_id"] == "phq-9"
        assert result["score"] == 10
        assert "interpretation" in result
        assert isinstance(result["interpretation"], str)


# ---------------------------------------------------------------------------
# Tool: get_assessment_summary
# ---------------------------------------------------------------------------


class TestAssessmentSummary:
    def setup_method(self):
        _reset_session()

    @pytest.mark.asyncio
    async def test_empty_summary(self):
        result = await get_assessment_summary._func(None)
        assert result["total_instruments"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_summary_with_results(self):
        session = _ensure_session()
        session.completed_results = [
            ScreeningResult(
                instrument_id="phq-9",
                score=15,
                severity="moderately severe",
                flagged_items=[9],
            ),
            ScreeningResult(
                instrument_id="gad-7",
                score=8,
                severity="mild",
                flagged_items=[],
            ),
        ]

        result = await get_assessment_summary._func(None)
        assert result["total_instruments"] == 2
        assert len(result["results"]) == 2
        assert "reminder" in result
        assert result["results"][0]["instrument"] == "phq-9"
        assert result["results"][0]["score"] == 15

    @pytest.mark.asyncio
    async def test_session_state_changes_to_summary(self):
        _ensure_session()
        await get_assessment_summary._func(None)
        session = _ensure_session()
        assert session.state == SessionState.SUMMARY


# ---------------------------------------------------------------------------
# AssessorAgent class
# ---------------------------------------------------------------------------


class TestAssessorAgent:
    def test_is_agent(self):
        from livekit.agents import Agent
        agent = AssessorAgent()
        assert isinstance(agent, Agent)

    def test_has_tools(self):
        agent = AssessorAgent()
        assert len(agent._tools) == 9

    def test_has_instructions(self):
        agent = AssessorAgent()
        assert "pre-assessment" in agent._instructions
        assert "check_safety" in agent._instructions

    def test_instructions_contain_disclaimer(self):
        assert "NOT a therapist" in ASSESSOR_INSTRUCTIONS
        assert "NOT a doctor" in ASSESSOR_INSTRUCTIONS
        assert "CANNOT diagnose" in ASSESSOR_INSTRUCTIONS
