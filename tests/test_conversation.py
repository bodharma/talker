import pytest
from talker.agents.conversation import ConversationAgent, ConversationContext
from talker.models.schemas import ScreeningResult


def test_conversation_context_creation():
    results = [
        ScreeningResult(
            instrument_id="phq-9",
            score=14,
            severity="moderate",
            raw_answers={},
            flagged_items=[9],
        )
    ]
    ctx = ConversationContext(screening_results=results)
    assert len(ctx.screening_results) == 1
    assert ctx.screening_results[0].severity == "moderate"


def test_conversation_agent_creates():
    agent = ConversationAgent()
    assert agent is not None


def test_build_system_prompt():
    results = [
        ScreeningResult(
            instrument_id="phq-9",
            score=14,
            severity="moderate",
            raw_answers={},
            flagged_items=[9],
        )
    ]
    ctx = ConversationContext(screening_results=results)
    agent = ConversationAgent()
    prompt = agent.build_system_prompt(ctx)
    assert "phq-9" in prompt.lower()
    assert "moderate" in prompt.lower()
    assert "not a medical" in prompt.lower() or "not a diagnosis" in prompt.lower()
