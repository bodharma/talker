from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.config import Settings


def create_agent_model(settings: Settings, role: str = "conversation") -> OpenAIChatModel:
    """Create a PydanticAI-compatible model via OpenRouter."""
    model_name = (
        settings.openrouter_model_conversation
        if role == "conversation"
        else settings.openrouter_model_screener
    )
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenAIChatModel(model_name, provider=provider)
