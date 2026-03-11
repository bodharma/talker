import logging

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.config import Settings

log = logging.getLogger(__name__)


def create_agent_model(settings: Settings, role: str = "conversation") -> OpenAIChatModel:
    """Create a PydanticAI-compatible model via OpenRouter or Ollama.

    Provider selection logic:
    1. If llm_provider is "ollama", use Ollama directly.
    2. If llm_provider is "openrouter" and an API key is set, use OpenRouter.
    3. Auto-fallback: if provider is "openrouter" but no API key, try Ollama.
    """
    provider_choice = settings.llm_provider

    # Auto-fallback: openrouter requested but no API key available
    if provider_choice == "openrouter" and not settings.openrouter_api_key:
        log.warning(
            "OpenRouter API key not set, falling back to Ollama (%s)",
            settings.ollama_chat_model,
        )
        provider_choice = "ollama"

    if provider_choice == "ollama":
        model_name = settings.ollama_chat_model
        provider = OpenAIProvider(
            base_url=f"{settings.ollama_base_url}/v1",
            api_key="ollama",  # Ollama ignores the key but the client requires one
        )
        return OpenAIChatModel(model_name, provider=provider)

    # Default: OpenRouter
    model_name = (
        settings.openrouter_model_conversation
        if role == "conversation"
        else settings.openrouter_model_screener
    )
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenAIChatModel(model_name, provider=provider)
