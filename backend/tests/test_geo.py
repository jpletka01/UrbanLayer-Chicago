import pytest

from backend.retrieval.geo import (
    COMMUNITY_AREAS,
    NEIGHBORHOOD_ALIASES,
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
