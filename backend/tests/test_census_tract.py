"""Tests for Census Reporter tract-level demographics."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import CensusTractDemographics
from backend.retrieval.neighborhood.census_tract import (
    _parse_age,
    _parse_education,
    _parse_income,
    _parse_race,
    _parse_transportation,
    fetch_census_tract,
)


SAMPLE_RESPONSE = {
    "data": {
        "14000US17031242400": {
            "B01001": {
                "estimate": {
                    "B01001001": 3084,
                    "B01001002": 1365, "B01001003": 0, "B01001004": 0,
                    "B01001005": 0, "B01001006": 0, "B01001007": 50,
                    "B01001008": 30, "B01001009": 20, "B01001010": 100,
                    "B01001011": 200, "B01001012": 250, "B01001013": 150,
                    "B01001014": 100, "B01001015": 80, "B01001016": 60,
                    "B01001017": 40, "B01001018": 20, "B01001019": 15,
                    "B01001020": 10, "B01001021": 5, "B01001022": 30,
                    "B01001023": 25, "B01001024": 15, "B01001025": 10,
                    "B01001026": 1719, "B01001027": 0, "B01001028": 0,
                    "B01001029": 0, "B01001030": 0, "B01001031": 60,
                    "B01001032": 40, "B01001033": 25, "B01001034": 120,
                    "B01001035": 300, "B01001036": 280, "B01001037": 180,
                    "B01001038": 120, "B01001039": 90, "B01001040": 70,
                    "B01001041": 50, "B01001042": 25, "B01001043": 18,
                    "B01001044": 12, "B01001045": 8, "B01001046": 35,
                    "B01001047": 30, "B01001048": 20, "B01001049": 15,
                },
                "error": {},
            },
            "B02001": {
                "estimate": {
                    "B02001001": 3084, "B02001002": 2588, "B02001003": 36,
                    "B02001004": 0, "B02001005": 189, "B02001006": 0,
                    "B02001007": 153, "B02001008": 118,
                },
                "error": {},
            },
            "B03003": {
                "estimate": {
                    "B03003001": 3084, "B03003002": 2755, "B03003003": 329,
                },
                "error": {},
            },
            "B15003": {
                "estimate": {
                    "B15003001": 2487,
                    "B15003002": 0, "B15003003": 0, "B15003004": 0,
                    "B15003005": 0, "B15003006": 0, "B15003007": 0,
                    "B15003008": 0, "B15003009": 0, "B15003010": 0,
                    "B15003011": 0, "B15003012": 0, "B15003013": 0,
                    "B15003014": 0, "B15003015": 0, "B15003016": 60,
                    "B15003017": 55, "B15003018": 20, "B15003019": 50,
                    "B15003020": 100, "B15003021": 80, "B15003022": 1115,
                    "B15003023": 774, "B15003024": 93, "B15003025": 140,
                },
                "error": {},
            },
            "B19001": {
                "estimate": {
                    "B19001001": 1621,
                    "B19001002": 30, "B19001003": 20, "B19001004": 15,
                    "B19001005": 25, "B19001006": 20, "B19001007": 30,
                    "B19001008": 25, "B19001009": 15, "B19001010": 10,
                    "B19001011": 80, "B19001012": 120, "B19001013": 193,
                    "B19001014": 287, "B19001015": 132, "B19001016": 260,
                    "B19001017": 309,
                },
                "error": {},
            },
            "B19013": {
                "estimate": {"B19013001": 110795},
                "error": {},
            },
            "B19301": {
                "estimate": {"B19301001": 71733},
                "error": {},
            },
            "B08301": {
                "estimate": {
                    "B08301001": 2357, "B08301002": 665, "B08301003": 619,
                    "B08301004": 46, "B08301005": 30, "B08301006": 10,
                    "B08301007": 5, "B08301008": 1, "B08301009": 0,
                    "B08301010": 358, "B08301011": 50, "B08301012": 250,
                    "B08301013": 50, "B08301014": 0, "B08301015": 0,
                    "B08301016": 20, "B08301017": 0, "B08301018": 100,
                    "B08301019": 200, "B08301020": 0, "B08301021": 1014,
                },
                "error": {},
            },
            "B17001": {
                "estimate": {
                    "B17001001": 3048, "B17001002": 271, "B17001031": 2777,
                },
                "error": {},
            },
            "B25077": {
                "estimate": {"B25077001": 628300},
                "error": {},
            },
            "B05002": {
                "estimate": {
                    "B05002001": 3084, "B05002002": 2651, "B05002013": 433,
                },
                "error": {},
            },
        },
        "16000US1714000": {
            "B19013": {"estimate": {"B19013001": 77902}, "error": {}},
        },
        "05000US17031": {
            "B19013": {"estimate": {"B19013001": 83498}, "error": {}},
        },
    },
    "geography": {
        "14000US17031242400": {"name": "Census Tract 2424, Cook, IL"},
    },
    "release": {"id": "acs2024_5yr", "name": "ACS 2024 5-year"},
    "tables": {},
}


def _tract_data():
    return SAMPLE_RESPONSE["data"]["14000US17031242400"]


class TestDistributionParsers:
    def test_age_distribution(self):
        dist, _ = _parse_age(_tract_data())
        assert len(dist) == 8
        labels = [b.label for b in dist]
        assert labels == ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
        assert all(b.value >= 0 for b in dist)

    def test_income_distribution(self):
        dist = _parse_income(_tract_data())
        assert len(dist) == 7
        assert dist[0].label == "Under $25K"
        assert dist[-1].label == "$200K+"
        assert all(b.value >= 0 for b in dist)

    def test_race_distribution(self):
        dist = _parse_race(_tract_data())
        assert len(dist) == 6
        labels = {b.label for b in dist}
        assert "White" in labels
        assert "Hispanic" in labels
        total_pct = sum(b.value for b in dist)
        assert 99 <= total_pct <= 101

    def test_education_distribution(self):
        dist, bach_pct = _parse_education(_tract_data())
        assert len(dist) == 5
        assert dist[-1].label == "Graduate+"
        assert bach_pct is not None
        assert bach_pct > 40

    def test_transportation_distribution(self):
        dist = _parse_transportation(_tract_data())
        assert len(dist) == 7
        labels = {b.label for b in dist}
        assert "Work from home" in labels
        assert "Public transit" in labels
        total_pct = sum(b.value for b in dist)
        assert 99 <= total_pct <= 101


class TestFetchCensusTract:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = SAMPLE_RESPONSE

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        result = await fetch_census_tract("17031242400", client=mock_client)

        assert result is not None
        assert result.tract_fips == "17031242400"
        assert result.tract_name == "Census Tract 2424, Cook, IL"
        assert result.population == 3084
        assert result.median_household_income == 110795
        assert result.per_capita_income == 71733
        assert result.median_home_value == 628300
        assert result.poverty_rate is not None
        assert result.poverty_rate > 0
        assert result.census_reporter_url == "https://censusreporter.org/profiles/14000US17031242400/"
        assert len(result.age_distribution) == 8
        assert len(result.income_distribution) == 7
        assert len(result.race_distribution) == 6
        assert len(result.education_distribution) == 5
        assert len(result.transportation_distribution) == 7
        assert result.city_median_income == 77902
        assert result.county_median_income == 83498

    @pytest.mark.asyncio
    async def test_not_found(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": {}, "geography": {}, "tables": {}}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        result = await fetch_census_tract("00000000000", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_api_failure(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")

        result = await fetch_census_tract("17031242400", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = SAMPLE_RESPONSE

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        r1 = await fetch_census_tract("17031242400", client=mock_client)
        r2 = await fetch_census_tract("17031242400", client=mock_client)

        assert r1 is not None
        assert r2 is not None
        assert r1.tract_fips == r2.tract_fips
        mock_client.get.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_census_reporter():
    result = await fetch_census_tract("17031242400")
    assert result is not None
    assert result.tract_fips == "17031242400"
    assert result.population is not None
    assert result.population > 0
    assert result.median_household_income is not None
    assert len(result.age_distribution) > 0
    assert len(result.income_distribution) > 0
