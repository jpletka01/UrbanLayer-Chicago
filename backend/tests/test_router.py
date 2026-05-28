import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from backend.router import _community_area_table, route
from backend.models import RetrievalPlan


class TestCommunityAreaTable:
    def test_includes_all_77_community_areas(self):
        table = _community_area_table()
        for ca_id in range(1, 78):
            assert f"  {ca_id}:" in table

    def test_includes_neighborhood_aliases(self):
        table = _community_area_table()
        assert "wicker park -> CA 24" in table
        assert "bucktown -> CA 22" in table
        assert "old town -> CA 8" in table

    def test_table_format(self):
        table = _community_area_table()
        assert "Official community areas" in table
        assert "Common neighborhood aliases" in table


class TestRoute:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.anthropic_api_key = "test-key"
        settings.router_model = "claude-sonnet-4-6"
        return settings

    @pytest.mark.asyncio
    async def test_parses_llm_response_to_retrieval_plan(self, mock_settings):
        llm_response = {
            "sources": ["crime_api", "311_api"],
            "location": {
                "raw": "Wicker Park",
                "type": "neighborhood",
                "resolved_community_area": 24,
            },
            "intent": "neighborhood_overview",
            "time_range_days": 90,
            "requires_disclaimer": False,
            "search_query": None,
            "clarification": None,
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = llm_response
                plan = await route("What's going on in Wicker Park?")

        assert isinstance(plan, RetrievalPlan)
        assert plan.sources == ["crime_api", "311_api"]
        assert plan.location.raw == "Wicker Park"
        assert plan.location.resolved_community_area == 24
        assert plan.location.resolved_community_area_name == "West Town"

    @pytest.mark.asyncio
    async def test_resolves_community_area_by_name_when_llm_misses(self, mock_settings):
        llm_response = {
            "sources": ["crime_api"],
            "location": {
                "raw": "Lincoln Park",
                "type": "community_area",
                "resolved_community_area": None,
            },
            "intent": "neighborhood_overview",
            "time_range_days": 90,
            "requires_disclaimer": False,
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = llm_response
                plan = await route("What's happening in Lincoln Park?")

        assert plan.location.resolved_community_area == 7
        assert plan.location.resolved_community_area_name == "Lincoln Park"

    @pytest.mark.asyncio
    async def test_resolves_neighborhood_alias(self, mock_settings):
        llm_response = {
            "sources": ["crime_api"],
            "location": {
                "raw": "Boystown",
                "type": "neighborhood",
                "resolved_community_area": None,
            },
            "intent": "neighborhood_overview",
            "time_range_days": 90,
            "requires_disclaimer": False,
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = llm_response
                plan = await route("Crime in Boystown")

        assert plan.location.resolved_community_area == 6
        assert plan.location.resolved_community_area_name == "Lake View"

    @pytest.mark.asyncio
    async def test_address_triggers_geocoder(self, mock_settings):
        llm_response = {
            "sources": ["crime_api"],
            "location": {
                "raw": "2400 N Milwaukee Ave",
                "type": "address",
                "resolved_address": "2400 N Milwaukee Ave",
                "resolved_community_area": None,
            },
            "intent": "incident_lookup",
            "time_range_days": 30,
            "requires_disclaimer": False,
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                with patch(
                    "backend.router.resolve_address_to_community_area",
                    new_callable=AsyncMock,
                ) as mock_geocode:
                    mock_llm.return_value = llm_response
                    mock_geocode.return_value = (22, (41.923, -87.704))
                    plan = await route("What's near 2400 N Milwaukee Ave?")

        assert plan.location.resolved_community_area == 22
        assert plan.location.resolved_community_area_name == "Logan Square"
        mock_geocode.assert_called_once()

    @pytest.mark.asyncio
    async def test_defaults_time_range_to_90(self, mock_settings):
        llm_response = {
            "sources": ["crime_api"],
            "location": {"raw": "Loop", "type": "community_area"},
            "intent": "neighborhood_overview",
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = llm_response
                plan = await route("What's happening in the Loop?")

        assert plan.time_range_days == 90

    @pytest.mark.asyncio
    async def test_clarification_intent_preserved(self, mock_settings):
        llm_response = {
            "sources": [],
            "location": {"raw": "", "type": "none"},
            "intent": "clarification_needed",
            "clarification": "Which neighborhood are you asking about?",
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = llm_response
                plan = await route("What's the crime like?")

        assert plan.intent == "clarification_needed"
        assert plan.clarification == "Which neighborhood are you asking about?"

    @pytest.mark.asyncio
    async def test_legal_question_sets_disclaimer(self, mock_settings):
        llm_response = {
            "sources": ["vector_search"],
            "location": {"raw": "West Town", "type": "community_area"},
            "intent": "legal_question",
            "requires_disclaimer": True,
            "search_query": "can I build a coach house",
        }

        with patch("backend.router.get_settings", return_value=mock_settings):
            with patch("backend.router._llm_plan", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = llm_response
                plan = await route("Can I build a coach house in West Town?")

        assert plan.requires_disclaimer is True
        assert plan.search_query == "can I build a coach house"
