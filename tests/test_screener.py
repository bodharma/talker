import pytest
from talker.agents.screener import ScreenerAgent
from talker.services.instruments import InstrumentLoader


@pytest.fixture
def loader():
    return InstrumentLoader("talker/instruments")


def test_screener_loads_instrument(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    assert agent.current_instrument is not None
    assert agent.current_question_index == 0


def test_screener_gets_first_question(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    q = agent.get_current_question()
    assert q is not None
    assert "interest or pleasure" in q.text.lower()


def test_screener_records_answer_and_advances(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    agent.record_answer(0)
    assert agent.current_question_index == 1


def test_screener_completes_instrument(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    for i in range(9):
        agent.record_answer(1)
    result = agent.get_result()
    assert result is not None
    assert result.instrument_id == "phq-9"
    assert result.score == 9
    assert result.severity == "mild"


def test_screener_is_complete(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("gad-7")
    for i in range(7):
        agent.record_answer(0)
    assert agent.is_complete()
