from talker.models.schemas import (
    SessionCreate, SessionState, ScreeningResult, InstrumentMetadata,
)

def test_session_create_defaults():
    session = SessionCreate()
    assert session.mode == "web"
    assert session.memory_consent is False
    assert session.voice_consent is False

def test_session_state_enum():
    assert SessionState.CREATED == "created"
    assert SessionState.INTAKE == "intake"
    assert SessionState.SCREENING == "screening"
    assert SessionState.FOLLOW_UP == "follow_up"
    assert SessionState.SUMMARY == "summary"
    assert SessionState.COMPLETED == "completed"
    assert SessionState.ABANDONED == "abandoned"
    assert SessionState.INTERRUPTED_BY_SAFETY == "interrupted_by_safety"

def test_screening_result_validation():
    result = ScreeningResult(
        instrument_id="phq-9", score=14, severity="moderate",
        raw_answers={"q1": 2, "q2": 3}, flagged_items=[9],
    )
    assert result.score == 14
    assert result.flagged_items == [9]

def test_instrument_metadata():
    meta = InstrumentMetadata(
        id="phq-9", name="Patient Health Questionnaire-9",
        description="Depression screening", item_count=9,
    )
    assert meta.id == "phq-9"
