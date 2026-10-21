from unittest.mock import AsyncMock, patch

import pytest

import backend.retrieval.neighborhood.demographics as demo_mod
from backend.models import ContextObject, DemographicsSummary
from backend.retrieval.neighborhood.demographics import fetch_demographics


@pytest.fixture(autouse=True)
def _clear_cache():
    demo_mod._cache = None
    yield
    demo_mod._cache = None


# A real t68z-cikk row's shape (columns as published; values for West Town-ish).
SAMPLE_ROW = {
    "acs_year": "2023",
    "community_area": "WEST TOWN",
    "under_25_000": "6000",
    "_25_000_to_49_999": "5000",
    "_50_000_to_74_999": "5000",
    "_75_000_to_125_000": "9000",
    "_125_000": "20000",
    "male_25_to_34": "12000",
    "female_25_to_34": "12000",
    "total_population": "87781",
    "white": "50000",
    "record_id": "2023_WEST TOWN",
}

# Fields this dataset never held, plus the kn9c-c2s2 (2008–2012) ones. Removed from
# DemographicsSummary 2026-10-20 (WS0 M1) so nothing implies we have them.
REMOVED = (
    "median_home_value", "median_gross_rent", "median_age", "poverty_rate",
    "unemployment_rate", "owner_occupied_pct", "bachelors_degree_pct", "vacancy_rate",
)


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_fetch_demographics_success(mock_socrata):
    mock_socrata.return_value = [SAMPLE_ROW]
    result = await fetch_demographics(24, client=AsyncMock())

    assert result is not None
    assert result.community_area == 24
    assert result.population == 87781
    # Bracket interpolation: 45,000 households; the 22,500th is 6,500 into the 9,000
    # in $75–125k → 75,000 + 6,500/9,000 × 50,000.
    assert result.median_household_income == 111_111
    assert result.acs_period == "2019–2023"


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_reads_only_the_acs_extract_never_kn9c(mock_socrata):
    """The 2008–2012 socioeconomic set (kn9c-c2s2) is never requested."""
    mock_socrata.return_value = [SAMPLE_ROW]
    await fetch_demographics(24, client=AsyncMock())
    assert mock_socrata.call_count == 1
    assert mock_socrata.call_args.args[0] == "t68z-cikk"
    assert all("kn9c" not in str(c) for c in mock_socrata.call_args_list)


def test_removed_fields_are_gone():
    fields = set(DemographicsSummary.model_fields)
    assert fields.isdisjoint(REMOVED)


def test_old_stored_context_still_parses():
    """Conversations saved before 2026-10-20 carry the removed keys; they must load."""
    old = {
        "community_area": 24, "community_area_name": "West Town", "population": 87781,
        "median_household_income": 82000, "median_home_value": None, "median_gross_rent": None,
        "median_age": 33.5, "poverty_rate": 12.4, "unemployment_rate": 6.1,
        "owner_occupied_pct": None, "bachelors_degree_pct": None, "vacancy_rate": None,
    }
    ctx = ContextObject.model_validate({"neighborhood": {"demographics": old}})
    d = ctx.neighborhood.demographics
    assert d.population == 87781
    assert d.acs_period is None
    assert all(not hasattr(d, f) for f in REMOVED)


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
    assert mock_socrata.call_count == 1  # one dataset, fetched once (cached)


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_handles_socrata_failure(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata down")
    result = await fetch_demographics(24, client=AsyncMock())
    assert result is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.demographics.socrata_get")
async def test_handles_missing_fields(mock_socrata):
    mock_socrata.return_value = [{"community_area": "24", "total_population": "50000"}]
    result = await fetch_demographics(24, client=AsyncMock())
    assert result is not None
    assert result.population == 50000
    assert result.median_household_income is None
    assert result.acs_period is None


# --- live integration test (real Socrata demographics dataset, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_demographics_live_lincoln_park():
    """Fetch real demographics for Lincoln Park (CA 7) from Socrata.

    The dataset (t68z-cikk) provides population and income brackets, not
    pre-computed medians; median_household_income is interpolated.
    """
    demo_mod._cache = None  # ensure fresh fetch
    result = await fetch_demographics(7)
    assert result is not None
    assert result.community_area == 7
    assert result.population is not None and result.population > 0
