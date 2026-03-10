from talker.services.llm import create_agent_model
from talker.config import Settings


def test_create_agent_model_returns_model():
    settings = Settings(openrouter_api_key="test-key")
    model = create_agent_model(settings, role="conversation")
    assert model is not None


def test_create_agent_model_screener():
    settings = Settings(openrouter_api_key="test-key")
    model = create_agent_model(settings, role="screener")
    assert model is not None
