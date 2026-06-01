"""Integration tests that hit real external APIs.

These tests verify actual connectivity and response parsing against live services.
They're slower and may incur costs (Anthropic) or rate limits (Socrata/Census).

Run with: pytest backend/tests/test_integration.py -v
Skip expensive tests: pytest backend/tests/test_integration.py -v -m "not expensive"
"""

import os
import pytest

pytestmark = pytest.mark.integration


def has_anthropic_key():
    from backend.config import get_settings
    try:
        settings = get_settings()
        return bool(settings.anthropic_api_key and settings.anthropic_api_key != "test-key")
    except Exception:
        return False


def qdrant_available():
    try:
        from qdrant_client import QdrantClient
        from backend.config import get_settings
        settings = get_settings()
        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        return True
    except Exception:
        return False


class TestSocrataIntegration:
    """Tests against the real Chicago Data Portal (Socrata) API."""

    @pytest.mark.asyncio
    async def test_crime_api_returns_data(self):
        from backend.retrieval.crime import crime_by_community_area

        result = await crime_by_community_area(24, days=30)

        assert isinstance(result, list)
        if result:
            assert "primary_type" in result[0]
            assert "count" in result[0]

    @pytest.mark.asyncio
    async def test_311_api_returns_data(self):
        from backend.retrieval.three11 import open_311_by_community_area

        result = await open_311_by_community_area(24)

        assert isinstance(result, list)
        if result:
            assert "sr_type" in result[0]
            assert "count" in result[0]

    @pytest.mark.asyncio
    async def test_permits_api_returns_data(self):
        from backend.retrieval.buildings import permits_by_community_area

        result = await permits_by_community_area(24, days=365)

        assert isinstance(result, list)
        if result:
            assert "work_description" in result[0] or "permit_type" in result[0]

    @pytest.mark.asyncio
    async def test_violations_api_returns_data(self):
        from backend.retrieval.buildings import violations_by_community_area

        result = await violations_by_community_area(24, days=365)

        assert isinstance(result, list)
        assert len(result) > 0, "Expected violations data for West Town"
        assert "violation_description" in result[0] or "violation_status" in result[0]

    @pytest.mark.asyncio
    async def test_business_api_returns_data(self):
        from backend.retrieval.business import businesses_by_community_area

        result = await businesses_by_community_area(32)  # Loop has lots of businesses

        assert isinstance(result, list)
        assert len(result) > 0
        assert "legal_name" in result[0] or "doing_business_as_name" in result[0]


class TestCensusGeocoderIntegration:
    """Tests against the real Census Geocoder API."""

    @pytest.mark.asyncio
    async def test_geocode_known_address(self):
        from backend.retrieval.geo import geocode_address

        coords = await geocode_address("2400 N Milwaukee Ave")

        assert coords is not None
        lat, lon = coords
        assert 41.9 < lat < 42.0  # Should be in Chicago
        assert -87.8 < lon < -87.6

    @pytest.mark.asyncio
    async def test_geocode_bad_address_returns_none(self):
        from backend.retrieval.geo import geocode_address

        coords = await geocode_address("99999 Fake Street Nowhere")

        assert coords is None

    @pytest.mark.asyncio
    async def test_resolve_address_to_community_area(self):
        from backend.retrieval.geo import resolve_address_to_community_area

        ca, coords = await resolve_address_to_community_area("233 S Wacker Dr")

        assert ca == 32  # The Loop
        assert coords is not None


class TestRouterIntegration:
    """Tests the router against real Anthropic API."""

    @pytest.mark.asyncio
    @pytest.mark.expensive
    @pytest.mark.skipif(not has_anthropic_key(), reason="No Anthropic API key")
    async def test_router_parses_neighborhood_query(self):
        from backend.router import route

        plan = await route("What's going on in Wicker Park?")

        assert plan.location.raw.lower() in ["wicker park", "west town"]
        assert plan.location.resolved_community_area == 24
        assert "crime_api" in plan.sources or "311_api" in plan.sources
        assert plan.intent in ["neighborhood_overview", "incident_lookup"]

    @pytest.mark.asyncio
    @pytest.mark.expensive
    @pytest.mark.skipif(not has_anthropic_key(), reason="No Anthropic API key")
    async def test_router_handles_legal_question(self):
        from backend.router import route

        plan = await route("Can I build a coach house in Lincoln Park?")

        assert plan.requires_disclaimer is True
        assert "vector_search" in plan.sources
        assert plan.intent == "legal_question"

    @pytest.mark.asyncio
    @pytest.mark.expensive
    @pytest.mark.skipif(not has_anthropic_key(), reason="No Anthropic API key")
    async def test_router_asks_for_clarification_when_no_location(self):
        from backend.router import route

        plan = await route("What's the crime like?")

        # Router should either ask for clarification or make a reasonable default
        assert plan.intent == "clarification_needed" or plan.location.resolved_community_area is not None


class TestQdrantIntegration:
    """Tests vector search against real Qdrant instance."""

    @pytest.mark.skipif(not qdrant_available(), reason="Qdrant not available")
    def test_qdrant_connection(self):
        from qdrant_client import QdrantClient
        from backend.config import get_settings

        settings = get_settings()
        client = QdrantClient(url=settings.qdrant_url)
        collections = client.get_collections()

        assert collections is not None

    @pytest.mark.skipif(not qdrant_available(), reason="Qdrant not available")
    @pytest.mark.asyncio
    async def test_semantic_search_returns_chunks(self):
        from backend.retrieval.vector_search import semantic_search

        results = await semantic_search("parking requirements for residential zones", top_k=3)

        # Will be empty if collection isn't populated, but shouldn't error
        assert isinstance(results, list)


class TestFullPipelineIntegration:
    """End-to-end test of the /chat endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.expensive
    @pytest.mark.skipif(not has_anthropic_key(), reason="No Anthropic API key")
    async def test_chat_endpoint_streams_response(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/chat",
            json={"message": "How much crime is in the Loop?", "history": []},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE events
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                import json
                events.append(json.loads(line[6:]))

        event_types = [e["type"] for e in events]
        assert "plan" in event_types
        assert "done" in event_types

        # Should have either context+tokens or an error
        assert "context" in event_types or "error" in event_types
