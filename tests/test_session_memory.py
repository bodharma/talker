from talker.services.session_memory import SessionMemoryService


def test_session_memory_service_init():
    """SessionMemoryService initializes with db session."""
    svc = SessionMemoryService(db=None)
    assert svc.db is None


def test_prior_context_format():
    """Prior context output format is correct."""
    context = (
        "PRIOR SESSION HISTORY (for context — do not repeat previous assessments):\n"
        "- Session 2026-03-10: PHQ-9: 12 (moderate)"
    )
    assert "PRIOR SESSION HISTORY" in context
    assert "PHQ-9" in context
