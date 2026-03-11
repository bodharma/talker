"""Tests for the Shard receptionist persona tools."""

import pytest

from talker.personas.receptionist import (
    BUILDING_INFO,
    DIRECTORY,
    ReceptionistAgent,
    _fuzzy_find,
    check_availability,
    get_building_info,
    get_weather,
    log_visitor,
    lookup_tenant,
    recognize_visitor,
    register_visitor,
)


# ---------------------------------------------------------------------------
# Directory lookup (pure function)
# ---------------------------------------------------------------------------


class TestDirectoryLookup:
    def test_exact_match_by_company(self):
        result = _fuzzy_find("deloitte")
        assert result is not None
        assert result["floor"] == 18
        assert result["company"] == "Deloitte"

    def test_exact_match_by_person(self):
        result = _fuzzy_find("Sarah Chen")
        assert result is not None
        assert result["floor"] == 18
        assert result["company"] == "Deloitte"

    def test_case_insensitive(self):
        result = _fuzzy_find("JAMES WARDLE")
        assert result is not None
        assert result["company"] == "Wardle Partners LLP"

    def test_substring_match(self):
        result = _fuzzy_find("wardle")
        assert result is not None
        assert result["floor"] == 12

    def test_company_name_search(self):
        result = _fuzzy_find("foresight")
        assert result is not None
        assert result["contact"] == "Priya Kapoor"

    def test_not_found(self):
        result = _fuzzy_find("John Nobody")
        assert result is None

    def test_whitespace_handling(self):
        result = _fuzzy_find("  tom blake  ")
        assert result is not None
        assert result["company"] == "Meridian Health Group"


# ---------------------------------------------------------------------------
# Tool functions (async — call _func directly, passing None for context)
# ---------------------------------------------------------------------------


class TestLookupTenantTool:
    @pytest.mark.asyncio
    async def test_found(self):
        result = await lookup_tenant._func(None, "deloitte")
        assert result["found"] is True
        assert result["floor"] == 18

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await lookup_tenant._func(None, "ghost company")
        assert result["found"] is False
        assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_fuzzy_match(self):
        result = await lookup_tenant._func(None, "wardle")
        assert result["found"] is True
        assert result["suite"] == "12A"


class TestCheckAvailabilityTool:
    @pytest.mark.asyncio
    async def test_known_unavailable(self):
        result = await check_availability._func(None, "James Wardle")
        assert result["available"] is False
        assert "out of office" in result["reason"]

    @pytest.mark.asyncio
    async def test_known_unavailable_meeting(self):
        result = await check_availability._func(None, "Priya Kapoor")
        assert result["available"] is False
        assert "meeting" in result["reason"]


class TestBuildingInfoTool:
    @pytest.mark.asyncio
    async def test_bathroom(self):
        result = await get_building_info._func(None, "bathroom")
        assert result["found"] is True
        assert "ground floor" in result["info"].lower()

    @pytest.mark.asyncio
    async def test_parking(self):
        result = await get_building_info._func(None, "parking")
        assert result["found"] is True
        assert "car park" in result["info"].lower()

    @pytest.mark.asyncio
    async def test_restaurant(self):
        result = await get_building_info._func(None, "restaurant")
        assert result["found"] is True
        assert "oblix" in result["info"].lower()

    @pytest.mark.asyncio
    async def test_unknown_topic(self):
        result = await get_building_info._func(None, "helicopter pad")
        assert result["found"] is False


class TestWeatherTool:
    @pytest.mark.asyncio
    async def test_fallback_without_api_key(self):
        result = await get_weather._func(None)
        assert "temperature_c" in result
        assert "description" in result
        assert result["source"] in ("mock", "fallback")


class TestVisitorLogTool:
    @pytest.mark.asyncio
    async def test_log_entry(self):
        result = await log_visitor._func(None, "Alex Test", "Sarah Chen", 18)
        assert result["logged"] is True
        assert "Alex Test" in result["message"]

    @pytest.mark.asyncio
    async def test_log_entry_untracked_without_db(self):
        result = await log_visitor._func(
            None, "Alex Test", "Sarah Chen", 18,
            visitor_email="alex@test.com", mood_impression="calm",
        )
        assert result["logged"] is True
        # Without DB factory, tracking is not available
        assert result["tracked"] is False


class TestRecognizeVisitorTool:
    @pytest.mark.asyncio
    async def test_no_db_returns_not_recognized(self):
        import talker.personas.receptionist as rec
        rec._db_session_factory = None
        result = await recognize_visitor._func(None, email="test@example.com")
        assert result["recognized"] is False

    @pytest.mark.asyncio
    async def test_no_params_returns_not_recognized(self):
        import talker.personas.receptionist as rec
        rec._db_session_factory = None
        result = await recognize_visitor._func(None)
        assert result["recognized"] is False


class TestRegisterVisitorTool:
    @pytest.mark.asyncio
    async def test_no_db_returns_not_registered(self):
        import talker.personas.receptionist as rec
        rec._db_session_factory = None
        result = await register_visitor._func(
            None, first_name="Jane", last_name="Doe", email="jane@example.com",
        )
        assert result["registered"] is False


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class TestReceptionistAgent:
    def test_agent_instantiation(self):
        agent = ReceptionistAgent()
        assert agent is not None

    def test_agent_has_instructions(self):
        agent = ReceptionistAgent()
        assert "Shard" in agent._instructions

    def test_agent_has_tools(self):
        agent = ReceptionistAgent()
        assert len(agent.tools) == 7

    def test_agent_accepts_extra_tools(self):
        from talker.capabilities.voice_analysis import get_voice_analysis
        agent = ReceptionistAgent(extra_tools=[get_voice_analysis])
        assert len(agent.tools) == 8


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


class TestDataIntegrity:
    def test_directory_has_multiple_tenants(self):
        companies = {v["company"] for v in DIRECTORY.values()}
        assert len(companies) >= 6

    def test_all_floors_are_positive(self):
        for entry in DIRECTORY.values():
            assert entry["floor"] > 0

    def test_building_info_covers_essentials(self):
        essentials = ["bathroom", "parking", "restaurant", "lift", "wifi"]
        for topic in essentials:
            assert topic in BUILDING_INFO, f"Missing building info for: {topic}"

    def test_directory_entries_have_required_fields(self):
        required = {"contact", "floor", "suite", "company", "type"}
        for key, entry in DIRECTORY.items():
            assert required.issubset(entry.keys()), f"Missing fields in '{key}': {required - entry.keys()}"
