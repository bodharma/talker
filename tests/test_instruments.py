import pytest
from talker.services.instruments import InstrumentLoader, InstrumentDefinition

def test_load_phq9():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    assert instrument.metadata.id == "phq-9"
    assert instrument.metadata.name == "Patient Health Questionnaire-9"
    assert len(instrument.questions) == 9
    assert len(instrument.response_options) > 0

def test_load_all_instruments():
    loader = InstrumentLoader("talker/instruments")
    instruments = loader.load_all()
    assert len(instruments) >= 4
    ids = [i.metadata.id for i in instruments]
    assert "phq-9" in ids
    assert "gad-7" in ids

def test_score_phq9_minimal():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    answers = {f"q{i}": 0 for i in range(1, 10)}
    result = instrument.score(answers)
    assert result.score == 0
    assert result.severity == "minimal"

def test_score_phq9_moderate():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    answers = {f"q{i}": 2 for i in range(1, 8)}
    answers["q8"] = 0
    answers["q9"] = 0
    result = instrument.score(answers)
    assert result.score == 14
    assert result.severity == "moderate"

def test_score_phq9_flags_item9():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    answers = {f"q{i}": 0 for i in range(1, 10)}
    answers["q9"] = 1
    result = instrument.score(answers)
    assert 9 in result.flagged_items
