from talker.agents.tools import (
    build_clinical_query,
    get_score_context,
    parse_instrument_selection,
)
from talker.services.instruments import InstrumentLoader


def test_parse_instrument_selection_valid():
    result = parse_instrument_selection(["phq-9", "gad-7"])
    assert result == ["phq-9", "gad-7"]


def test_parse_instrument_selection_dedupes():
    result = parse_instrument_selection(["phq-9", "phq-9", "gad-7"])
    assert result == ["phq-9", "gad-7"]


def test_parse_instrument_selection_filters_invalid():
    loader = InstrumentLoader("talker/instruments")
    valid_ids = {i.metadata.id for i in loader.load_all()}
    result = parse_instrument_selection(["phq-9", "fake-instrument"], valid_ids=valid_ids)
    assert result == ["phq-9"]


def test_get_score_context_phq9():
    loader = InstrumentLoader("talker/instruments")
    context = get_score_context("phq-9", 14, loader)
    assert "moderate" in context.lower()
    assert "phq-9" in context.lower()


def test_get_score_context_minimal():
    loader = InstrumentLoader("talker/instruments")
    context = get_score_context("phq-9", 2, loader)
    assert "minimal" in context.lower()


def test_build_clinical_query():
    query = build_clinical_query(
        symptoms=["insomnia", "low mood", "fatigue"],
        instrument_id="phq-9",
    )
    assert "insomnia" in query
    assert "PHQ-9" in query


def test_build_clinical_query_no_instrument():
    query = build_clinical_query(symptoms=["anxiety", "worry"])
    assert "anxiety" in query
    assert "screening" not in query.lower()
