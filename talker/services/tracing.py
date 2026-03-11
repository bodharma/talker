import logging

from langfuse import Langfuse

from talker.config import Settings

log = logging.getLogger(__name__)

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


def create_trace(
    *,
    session_id: str,
    agent_name: str,
    user_id: str | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
):
    """Create a Langfuse trace for an agent interaction.

    Returns the trace object (or None if Langfuse is not configured).
    The trace_id can be used later to attach scores.
    """
    lf = get_langfuse()
    if lf is None:
        return None

    kwargs: dict = {
        "name": f"talker-{agent_name}",
        "session_id": session_id,
        "metadata": {"agent": agent_name},
    }
    if user_id:
        kwargs["user_id"] = user_id
    if user_email or user_name:
        kwargs["metadata"]["user_email"] = user_email
        kwargs["metadata"]["user_name"] = user_name

    return lf.trace(**kwargs)


def create_score(
    *,
    trace_id: str,
    name: str = "user-feedback",
    value: float,
    comment: str | None = None,
):
    """Attach a user feedback score to a Langfuse trace."""
    lf = get_langfuse()
    if lf is None:
        return
    try:
        lf.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            data_type="NUMERIC",
            comment=comment,
        )
        lf.flush()
    except Exception as e:
        log.warning("Failed to create Langfuse score: %s", e)


def get_prompt(name: str, fallback: str) -> str:
    """Fetch a prompt from Langfuse by name. Falls back to the hardcoded string
    if Langfuse is not configured or the prompt doesn't exist yet."""
    lf = get_langfuse()
    if lf is None:
        return fallback
    try:
        prompt = lf.get_prompt(name)
        return prompt.compile()
    except Exception as e:
        log.debug("Langfuse prompt '%s' not found, using fallback: %s", name, e)
        return fallback
