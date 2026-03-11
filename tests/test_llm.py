from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.config import Settings
from talker.services.llm import create_agent_model


def test_create_agent_model_returns_model():
    settings = Settings(openrouter_api_key="test-key")
    model = create_agent_model(settings, role="conversation")
    assert model is not None


def test_create_agent_model_screener():
    settings = Settings(openrouter_api_key="test-key")
    model = create_agent_model(settings, role="screener")
    assert model is not None


def test_create_agent_model_openrouter_uses_correct_provider():
    settings = Settings(openrouter_api_key="test-key", llm_provider="openrouter")
    model = create_agent_model(settings, role="conversation")
    assert isinstance(model._provider, OpenRouterProvider)
    assert model.model_name == settings.openrouter_model_conversation


def test_create_agent_model_ollama():
    """When provider is ollama, returns model pointed at Ollama base_url."""
    settings = Settings(
        llm_provider="ollama",
        ollama_chat_model="llama3.2",
        ollama_base_url="http://localhost:11434",
    )
    model = create_agent_model(settings, role="conversation")
    assert model.model_name == "llama3.2"
    assert isinstance(model._provider, OpenAIProvider)
    assert "localhost:11434/v1" in str(model._provider.base_url)


def test_create_agent_model_fallback():
    """When openrouter key is empty and ollama is configured, falls back to Ollama."""
    settings = Settings(
        llm_provider="openrouter",
        openrouter_api_key="",
        ollama_chat_model="mistral",
        ollama_base_url="http://localhost:11434",
    )
    model = create_agent_model(settings, role="conversation")
    # Should have fallen back to ollama
    assert model.model_name == "mistral"
    assert isinstance(model._provider, OpenAIProvider)


def test_create_agent_model_ollama_ignores_role():
    """Ollama always uses ollama_chat_model regardless of role."""
    settings = Settings(
        llm_provider="ollama",
        ollama_chat_model="llama3.2",
    )
    conv_model = create_agent_model(settings, role="conversation")
    screener_model = create_agent_model(settings, role="screener")
    assert conv_model.model_name == screener_model.model_name == "llama3.2"
