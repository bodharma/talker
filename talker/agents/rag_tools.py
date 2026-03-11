"""RAG-powered tool functions for agents."""


def build_rag_enhanced_prompt(base_prompt: str, rag_context: str) -> str:
    """Enhance an agent's system prompt with RAG-retrieved knowledge."""
    if not rag_context:
        return base_prompt

    return f"""{base_prompt}

CLINICAL KNOWLEDGE (use this to inform your responses, but do not quote directly):
{rag_context}"""
