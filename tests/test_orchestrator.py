from talker.agents.orchestrator import Orchestrator
from talker.models.schemas import SessionState


def test_orchestrator_initial_state():
    orch = Orchestrator(instruments_dir="talker/instruments")
    assert orch.state == SessionState.CREATED


def test_orchestrator_start_creates_intake():
    orch = Orchestrator(instruments_dir="talker/instruments")
    greeting = orch.start()
    assert orch.state == SessionState.INTAKE
    assert "not a medical" in greeting.lower() or "not a diagnosis" in greeting.lower()


def test_orchestrator_select_instruments():
    orch = Orchestrator(instruments_dir="talker/instruments")
    orch.start()
    orch.select_instruments(["phq-9", "gad-7"])
    assert orch.state == SessionState.SCREENING
    assert len(orch.instrument_queue) == 2


def test_orchestrator_full_checkup():
    orch = Orchestrator(instruments_dir="talker/instruments")
    orch.start()
    orch.select_full_checkup()
    assert orch.state == SessionState.SCREENING
    assert len(orch.instrument_queue) >= 4


def test_orchestrator_state_transitions():
    orch = Orchestrator(instruments_dir="talker/instruments")
    assert orch.state == SessionState.CREATED
    orch.start()
    assert orch.state == SessionState.INTAKE
    orch.select_instruments(["phq-9"])
    assert orch.state == SessionState.SCREENING
