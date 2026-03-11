from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.config import get_settings


class VoiceAnswerMapping(BaseModel):
    value: int = Field(description="The numeric value from the response options that best matches")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the mapping (0.0-1.0)"
    )
    reasoning: str = Field(description="Brief explanation of why this mapping was chosen")


MAPPING_SYSTEM_PROMPT = (
    "You are mapping a user's spoken response to a screening questionnaire option. "
    "The user answered verbally and may have used informal language. "
    "Match their response to the closest option and provide your confidence level. "
    "If the response is ambiguous or unclear, set confidence below 0.7."
)


def build_mapping_prompt(
    question: str,
    options: list[dict],
    transcript: str,
) -> str:
    options_text = "\n".join(f"  {opt['value']}: {opt['text']}" for opt in options)
    return (
        f"Question: {question}\n\n"
        f"Response options:\n{options_text}\n\n"
        f'User\'s spoken response: "{transcript}"\n\n'
        f"Map this response to the best matching option."
    )


async def map_voice_answer(
    question: str,
    options: list[dict],
    transcript: str,
) -> VoiceAnswerMapping:
    """Use LLM to map a voice transcript to a screening scale value."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        return VoiceAnswerMapping(value=0, confidence=0.0, reasoning="No LLM available")

    model = OpenAIChatModel(
        settings.openrouter_model_screener,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    )
    agent = Agent(model, system_prompt=MAPPING_SYSTEM_PROMPT, output_type=VoiceAnswerMapping)
    prompt = build_mapping_prompt(question, options, transcript)
    result = await agent.run(prompt)
    return result.output
