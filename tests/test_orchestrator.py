import uuid
from datetime import UTC, datetime

from talker.agents.orchestrator import Orchestrator
from talker.models.schemas import SessionData, SessionState


def _make_session(**kwargs) -> SessionData:
    defaults = {
        "id": uuid.uuid4(),
        "state": SessionState.SCREENING,
        "instrument_queue": ["phq-9"],
        "current_instrument_index": 0,
        "completed_results": [],
        "chat_messages": [],
        "current_answers": {},
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return SessionData(**defaults)


def test_get_screening_question():
    orch = Orchestrator(instruments_dir="talker/instruments")
    session = _make_session(instrument_queue=["phq-9"])
    q = orch.get_current_screening_question(session)
    assert q is not None
    assert q["instrument_id"] == "phq-9"
    assert q["question_number"] == 1


def test_get_screening_question_wrong_state():
    orch = Orchestrator(instruments_dir="talker/instruments")
    session = _make_session(state=SessionState.FOLLOW_UP)
    q = orch.get_current_screening_question(session)
    assert q is None


def test_submit_answer_next_question():
    orch = Orchestrator(instruments_dir="talker/instruments")
    session = _make_session(instrument_queue=["phq-9"])
    result = orch.submit_screening_answer(session, 1)
    assert result["action"] == "next_question"


def test_submit_answer_completes_instrument():
    orch = Orchestrator(instruments_dir="talker/instruments")
    answers = {f"q{i+1}": 1 for i in range(8)}
    session = _make_session(
        instrument_queue=["phq-9"],
        current_answers=answers,
    )
    result = orch.submit_screening_answer(session, 1)
    assert result["action"] == "screening_complete"
    assert result["result"] is not None
    assert result["result"].score == 9


def test_submit_answer_moves_to_next_instrument():
    orch = Orchestrator(instruments_dir="talker/instruments")
    answers = {f"q{i+1}": 0 for i in range(8)}
    session = _make_session(
        instrument_queue=["phq-9", "gad-7"],
        current_answers=answers,
    )
    result = orch.submit_screening_answer(session, 0)
    assert result["action"] == "next_instrument"
    assert result["instrument_id"] == "gad-7"
    assert result["next_index"] == 1


def test_get_all_instrument_ids():
    orch = Orchestrator(instruments_dir="talker/instruments")
    ids = orch.get_all_instrument_ids()
    assert "phq-9" in ids
    assert "gad-7" in ids
    assert len(ids) >= 4


def test_parse_triage_result():
    orch = Orchestrator(instruments_dir="talker/instruments")
    result = orch.parse_triage_result(["phq-9", "gad-7", "invalid-one"])
    assert "phq-9" in result
    assert "gad-7" in result
    assert "invalid-one" not in result
