from langfuse import Langfuse

from talker.config import Settings


_langfuse: Langfuse | None = None


def init_langfuse(settings: Settings) -> Langfuse | None:
    """Initialize Langfuse client. Returns None if not configured."""
    global _langfuse
    if not settings.langfuse_secret_key:
        return None
    _langfuse = Langfuse(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )
    return _langfuse


def get_langfuse() -> Langfuse | None:
    return _langfuse


def create_trace(session_id: int, agent_name: str):
    """Create a Langfuse trace for an agent interaction."""
    lf = get_langfuse()
    if lf is None:
        return None
    return lf.trace(
        name=f"talker-{agent_name}",
        session_id=str(session_id),
        metadata={"agent": agent_name},
    )
