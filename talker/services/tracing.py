import logging
from dataclasses import dataclass

from langfuse import Langfuse, propagate_attributes

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


@dataclass
class TraceRef:
    """Lightweight reference to a Langfuse trace, exposing just the id."""
    id: str


def create_trace(
    *,
    session_id: str,
    agent_name: str,
    user_id: str | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
) -> TraceRef | None:
    """Create a Langfuse trace for an agent interaction.

    Returns a TraceRef with .id (or None if Langfuse is not configured).
    The trace_id can be used later to attach scores.

    Langfuse v4 uses OpenTelemetry-based span tracing. We create a root
    span with propagated attributes (user_id, session_id) to register
    the trace with all metadata.
    """
    lf = get_langfuse()
    if lf is None:
        return None

    trace_id = Langfuse.create_trace_id()
    metadata = {"agent": agent_name}
    if user_email:
        metadata["user_email"] = user_email
    if user_name:
        metadata["user_name"] = user_name

    with lf.start_as_current_observation(
        name=f"talker-{agent_name}",
        trace_context={"trace_id": trace_id},
        input={"session_id": session_id, "agent": agent_name},
        metadata=metadata,
    ):
        with propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            trace_name=f"talker-{agent_name}",
        ):
            pass  # span registers the trace; no work needed inside

    lf.flush()
    return TraceRef(id=trace_id)


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
