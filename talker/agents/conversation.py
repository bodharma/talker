from pydantic import BaseModel, Field

from talker.models.schemas import ConversationObservation, ScreeningResult


class ConversationContext(BaseModel):
    screening_results: list[ScreeningResult] = Field(default_factory=list)
    prior_observations: list[ConversationObservation] = Field(default_factory=list)


class ConversationAgent:
    """Conducts open-ended follow-up conversations based on screening results.

    Uses an LLM to explore flagged areas. The actual LLM call is handled
    externally (by the orchestrator) — this agent builds prompts and
    parses responses.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are a compassionate mental health pre-assessment assistant conducting a follow-up conversation.

IMPORTANT DISCLAIMERS:
- You are NOT a medical professional and this is NOT a diagnosis
- You are helping the user understand their symptoms to prepare for a professional consultation
- Never diagnose or prescribe treatment
- If you detect any crisis indicators, immediately provide crisis resources

SCREENING RESULTS:
{screening_summary}

YOUR ROLE:
- Explore the flagged areas conversationally: duration, triggers, daily life impact, history
- Be warm, non-judgmental, and patient
- Ask one question at a time
- Validate the user's experiences
- Focus on understanding, not fixing

Respond conversationally. Keep responses concise (2-3 sentences max) and end with a single follow-up question."""

    def build_system_prompt(self, context: ConversationContext) -> str:
        summaries = []
        for result in context.screening_results:
            summary = f"- {result.instrument_id}: score {result.score}, severity: {result.severity}"
            if result.flagged_items:
                summary += f" (flagged items: {result.flagged_items})"
            summaries.append(summary)

        screening_summary = "\n".join(summaries) if summaries else "No screening results available."

        return self.SYSTEM_PROMPT_TEMPLATE.format(screening_summary=screening_summary)

    def build_system_prompt_with_rag(
        self, context: ConversationContext, rag_context: str
    ) -> str:
        """Build system prompt enhanced with RAG-retrieved knowledge."""
        from talker.agents.rag_tools import build_rag_enhanced_prompt

        base = self.build_system_prompt(context)
        return build_rag_enhanced_prompt(base, rag_context)
