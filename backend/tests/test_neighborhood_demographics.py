from unittest.mock import AsyncMock, patch

import pytest

import backend.retrieval.neighborhood.demographics as demo_mod
from backend.retrieval.neighborhood.demographics import fetch_demographics


@pytest.fixture(autouse=True)
def _clear_cache():
    demo_mod._cache = None
    yield
    demo_mod._cache = None


SAMPLE_ROW = {
    "community_area": "24",
    "community_area_name": "West Town",
    "population": "87781",
    "median_household_income": "82000",
    "median_home_value": "350000",
    "median_gross_rent": "1250",
    "median_age": "33.5",
    "below_poverty_level": "8778",
    "unemployed": "2500",
    "in_labor_force": "50000",
    "owner_occupied_housing_units": "15000",
    "total_housing_units": "42000",
    "bachelors_degree_or_higher": "35000",
    "population_25_years_and_over": "60000",
    "vacant_housing_units": "2100",
}


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_fetch_demographics_success(mock_socrata):
    mock_socrata.return_value = [SAMPLE_ROW]
    result = await fetch_demographics(24, client=AsyncMock())

    assert result is not None
    assert result.community_area == 24
    assert result.community_area_name == "West Town"
    assert result.population == 87781
    assert result.median_household_income == 82000
    assert result.median_home_value == 350000
    assert result.median_gross_rent == 1250
    assert result.median_age == 33.5
    assert result.poverty_rate == pytest.approx(10.0, abs=0.1)
    assert result.unemployment_rate == pytest.approx(5.0, abs=0.1)
    assert result.owner_occupied_pct == pytest.approx(35.7, abs=0.1)
    assert result.bachelors_degree_pct == pytest.approx(58.3, abs=0.1)
    assert result.vacancy_rate == pytest.approx(5.0, abs=0.1)


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_unknown_community_area(mock_socrata):
    mock_socrata.return_value = [SAMPLE_ROW]
    result = await fetch_demographics(99, client=AsyncMock())
    assert result is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_cache_populated_on_first_call(mock_socrata):
    mock_socrata.return_value = [SAMPLE_ROW]
    await fetch_demographics(24, client=AsyncMock())
    await fetch_demographics(24, client=AsyncMock())
    assert mock_socrata.call_count == 2  # demographics + socioeconomic, called once total (cached)


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_handles_socrata_failure(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata down")
    result = await fetch_demographics(24, client=AsyncMock())
    assert result is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_handles_missing_fields(mock_socrata):
    mock_socrata.return_value = [{"community_area": "24", "population": "50000"}]
    result = await fetch_demographics(24, client=AsyncMock())
    assert result is not None
    assert result.population == 50000
    assert result.median_household_income is None
    assert result.poverty_rate is None


# --- live integration test (real Socrata demographics dataset, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_demographics_live_lincoln_park():
    """Fetch real demographics for Lincoln Park (CA 7) from Socrata.

    Note: The dataset (t68z-cikk) provides population and income
    distribution brackets but not pre-computed median values. Fields
    like median_household_income will be None with this dataset.
    """
    demo_mod._cache = None  # ensure fresh fetch
    result = await fetch_demographics(7)
    assert result is not None
    assert result.community_area == 7
    assert result.population is not None and result.population > 0
