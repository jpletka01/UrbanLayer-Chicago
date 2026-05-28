import pytest

from backend.retrieval.geo import (
    COMMUNITY_AREAS,
    NEIGHBORHOOD_ALIASES,
    community_area_bounds,
    community_area_by_name,
)


class TestCommunityAreaByName:
    def test_exact_community_area_match(self):
        assert community_area_by_name("West Town") == 24
        assert community_area_by_name("Lincoln Park") == 7
        assert community_area_by_name("Loop") == 32

    def test_case_insensitive_community_area(self):
        assert community_area_by_name("west town") == 24
        assert community_area_by_name("LINCOLN PARK") == 7
        assert community_area_by_name("lOoP") == 32

    def test_neighborhood_alias_exact(self):
        assert community_area_by_name("wicker park") == 24
        assert community_area_by_name("bucktown") == 22
        assert community_area_by_name("old town") == 8
        assert community_area_by_name("boystown") == 6

    def test_neighborhood_alias_case_insensitive(self):
        assert community_area_by_name("Wicker Park") == 24
        assert community_area_by_name("BUCKTOWN") == 22
        assert community_area_by_name("Old Town") == 8

    def test_partial_match_substring(self):
        assert community_area_by_name("garfield") in [26, 27, 56]
        assert community_area_by_name("englewood") in [67, 68]

    def test_empty_string_returns_none(self):
        assert community_area_by_name("") is None

    def test_unknown_location_returns_none(self):
        assert community_area_by_name("Atlantis") is None
        assert community_area_by_name("New York") is None
        assert community_area_by_name("xyz123") is None


class TestCommunityAreasData:
    def test_all_77_community_areas_present(self):
        assert len(COMMUNITY_AREAS) == 77
        assert set(COMMUNITY_AREAS.keys()) == set(range(1, 78))

    def test_sample_community_area_names(self):
        assert COMMUNITY_AREAS[1] == "Rogers Park"
        assert COMMUNITY_AREAS[32] == "Loop"
        assert COMMUNITY_AREAS[77] == "Edgewater"

    def test_aliases_map_to_valid_community_areas(self):
        for alias, ca in NEIGHBORHOOD_ALIASES.items():
            assert 1 <= ca <= 77, f"Alias {alias} maps to invalid CA {ca}"
            assert ca in COMMUNITY_AREAS


class TestCommunityAreaBounds:
    def test_returns_bounds_for_valid_ca(self):
        bounds = community_area_bounds(24)  # West Town
        assert bounds is not None
        min_lat, min_lon, max_lat, max_lon = bounds
        assert min_lat < max_lat
        assert min_lon < max_lon
        assert 41.0 < min_lat < 42.5
        assert -88.0 < min_lon < -87.0

    def test_returns_none_for_invalid_ca(self):
        assert community_area_bounds(0) is None
        assert community_area_bounds(78) is None
        assert community_area_bounds(-1) is None

    def test_bounds_reasonable_for_known_ca(self):
        bounds = community_area_bounds(32)  # Loop
        assert bounds is not None
        min_lat, min_lon, max_lat, max_lon = bounds
        assert 41.85 < min_lat < 41.90
        assert max_lat - min_lat < 0.05  # Loop is small


class TestGeocodeAddressSuggestions:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_suggestions_for_valid_address(self):
        from backend.retrieval.geo import geocode_address_suggestions

        results = await geocode_address_suggestions("2400 N Milwaukee Ave")
        assert len(results) > 0
        assert "address" in results[0]
        assert "lat" in results[0]
        assert "lon" in results[0]
        assert "MILWAUKEE" in results[0]["address"].upper()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_empty_for_short_query(self):
        from backend.retrieval.geo import geocode_address_suggestions

        results = await geocode_address_suggestions("24")
        assert results == []

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_empty_for_invalid_address(self):
        from backend.retrieval.geo import geocode_address_suggestions

        results = await geocode_address_suggestions("xyznonexistent12345")
        assert results == []
