"""Tests for the property domain orchestrator."""

import datetime

import pytest
from unittest.mock import AsyncMock, patch

from backend.models import PropertySummary
from backend.retrieval.property import property_domain, _build_summary, _safe_int, _safe_float


SAMPLE_PARCEL = {
    "pin14": "14241020170000",
    "bldg_class": "2-11",
    "bldg_sqft": 2400,
    "land_sqft": 3200,
    "total_value": 350000,
    "address": "443 W WRIGHTWOOD AVE",
}

# Mirrors the real x54s-btds schema AND value domains (verified 2026-07-02):
# `char_apts` is a decoded word ("Two".."Six", 211/212 only), `char_type_resd`
# is "1 Story"/"1.5 Story"/"2 Story"/"3 Story +"/"Split Level", `char_use` is
# "Single-Family"/"Multi-Family", `char_ncu` is the COMMERCIAL unit count
# (previously mis-mapped to stories). No char_age/char_class_description.
SAMPLE_CHARS = {
    "pin": "14241020170000",
    "year": "2024",
    "char_bldg_sf": "2600",
    "char_land_sf": "3200",
    "char_ncu": "3",
    "char_apts": "Two",
    "char_type_resd": "2 Story",
    "char_use": "Multi-Family",
    "char_rooms": "8",
    "char_beds": "4",
    "char_fbath": "2",
    "char_hbath": "1",
    "char_yrblt": "1929",
}

# Real uzyt-m557 schema uses `year`, not `tax_year`.
SAMPLE_ASSESSMENTS = [
    {"year": "2024", "class": "211", "mailed_land": "10000", "mailed_bldg": "35000", "mailed_tot": "45000"},
    {"year": "2023", "class": "211", "mailed_land": "9500", "mailed_bldg": "33000", "mailed_tot": "42500"},
]

SAMPLE_SALES = [
    {"sale_date": "2023-06-15T00:00:00.000", "sale_price": "450000", "deed_type": "Warranty"},
    {"sale_date": "2018-03-01T00:00:00.000", "sale_price": "320000", "deed_type": "Warranty"},
]


@pytest.mark.asyncio
async def test_assembles_full_summary():
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.return_value = SAMPLE_CHARS
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)

        assert result is not None
        assert isinstance(result, PropertySummary)
        assert result.pin14 == "14241020170000"
        assert result.address == "443 W WRIGHTWOOD AVE"
        assert result.bldg_sqft == 2600  # CCAO overrides GIS
        assert result.stories == 2.0  # from char_type_resd, NOT char_ncu
        assert result.units == 2  # decoded from char_apts word "Two"
        assert result.commercial_units == 3  # char_ncu surfaced honestly
        assert result.rooms == 8
        assert result.bedrooms == 4
        assert result.full_baths == 2
        assert result.half_baths == 1
        assert result.year_built == 1929
        assert result.bldg_age == datetime.date.today().year - 1929
        assert result.tax_exempt is False
        assert result.total_assessed_value == 45000.0
        assert len(result.assessment_history) == 2
        assert result.assessment_history[0].year == 2024
        assert result.assessment_history[0].total == 45000.0
        assert len(result.sales_history) == 2
        assert result.sales_history[0].price == 450000.0


@pytest.mark.asyncio
async def test_returns_none_when_no_parcel():
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel:
        mock_parcel.return_value = None
        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)
        assert result is None


@pytest.mark.asyncio
async def test_handles_partial_ccao_failure():
    """If one CCAO query fails, the others still contribute."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.side_effect = Exception("timeout")
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)

        assert result is not None
        assert result.pin14 == "14241020170000"
        assert result.bldg_sqft == 2400  # falls back to GIS value
        assert result.stories is None  # no CCAO enrichment
        assert len(result.assessment_history) == 2
        assert len(result.sales_history) == 2


@pytest.mark.asyncio
async def test_handles_all_ccao_failure():
    """If all CCAO queries fail, we still get GIS parcel data."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.side_effect = Exception("timeout")
        mock_assess.side_effect = Exception("timeout")
        mock_sales.side_effect = Exception("timeout")

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)

        assert result is not None
        assert result.pin14 == "14241020170000"
        assert result.bldg_sqft == 2400
        assert result.assessment_history == []
        assert result.sales_history == []


@pytest.mark.asyncio
async def test_pin14_passed_to_ccao_queries():
    """Verify the PIN from parcel lookup is forwarded to all CCAO sub-queries."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = {"pin14": "99998887770000", "address": "TEST"}
        mock_chars.return_value = None
        mock_assess.return_value = []
        mock_sales.return_value = []

        client = AsyncMock()
        await property_domain(41.93, -87.64, client=client)

        mock_chars.assert_awaited_once()
        assert mock_chars.call_args[0][0] == "99998887770000"
        mock_assess.assert_awaited_once()
        assert mock_assess.call_args[0][0] == "99998887770000"
        mock_sales.assert_awaited_once()
        assert mock_sales.call_args[0][0] == "99998887770000"


def test_safe_int_handles_various_inputs():
    assert _safe_int("2400") == 2400
    assert _safe_int("2400.5") == 2400
    assert _safe_int(2400) == 2400
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("N/A") is None


def test_safe_float_handles_various_inputs():
    assert _safe_float("45000.50") == 45000.50
    assert _safe_float(45000) == 45000.0
    assert _safe_float(None) is None
    assert _safe_float("") is None
    assert _safe_float("N/A") is None


def test_decode_stories_from_type_resd():
    from backend.retrieval.property import _decode_stories
    assert _decode_stories({"char_type_resd": "1 Story"}) == 1.0
    assert _decode_stories({"char_type_resd": "1.5 Story"}) == 1.5
    assert _decode_stories({"char_type_resd": "2 Story"}) == 2.0
    assert _decode_stories({"char_type_resd": "3 Story +"}) == 3.0
    # No defensible number for these — None over wrong
    assert _decode_stories({"char_type_resd": "Split Level"}) is None
    assert _decode_stories({"char_type_resd": None}) is None
    assert _decode_stories({}) is None
    # char_ncu must never leak into stories again (the 2026-07-02 benchmark bug)
    assert _decode_stories({"char_ncu": "3"}) is None


def test_build_summary_geometry_and_fallback_merge():
    """Non-residential parcel (no chars): land from geometry, bldg from
    commercial valuation, year/stories from footprints — each provenance-labeled.
    Assessor values, when present, must win (second case)."""
    bare_parcel = {"pin14": "20331000020000", "bldg_class": "517", "address": None}
    fallbacks = {
        "condo": None,
        "commercial_sqft": 12500,
        "footprint": {"stories": 2, "year_built": 1924, "bldg_sqft": None},
    }
    geo = {"land_sqft_geom": 7381, "parcel_geometry": {"type": "Polygon", "coordinates": []},
           "geom_year": 2024}
    s = _build_summary(bare_parcel, None, [], [], None,
                       geometry_facts=geo, building_fallbacks=fallbacks)
    assert s.land_sqft == 7381 and s.land_sqft_source == "geometry"
    assert s.bldg_sqft == 12500 and s.bldg_sqft_source == "commercial_valuation"
    assert s.year_built == 1924 and s.year_built_source == "footprint"
    assert s.stories == 2.0 and s.stories_source == "footprint"
    assert s.parcel_geometry == geo["parcel_geometry"]

    # Assessor data present -> fallbacks must NOT override
    s2 = _build_summary(SAMPLE_PARCEL, SAMPLE_CHARS, [], [], None,
                        geometry_facts=geo, building_fallbacks=fallbacks)
    assert s2.bldg_sqft == 2600 and s2.bldg_sqft_source == "assessor"
    assert s2.land_sqft == 3200 and s2.land_sqft_source == "assessor"
    assert s2.year_built == 1929 and s2.year_built_source == "assessor"
    assert s2.stories == 2.0 and s2.stories_source == "assessor"


def test_build_summary_condo_unit_facts():
    """Condo PIN (no x54s row): unit sqft/year/bedrooms from the condo dataset."""
    condo_parcel = {"pin14": "17102140281234", "bldg_class": "299", "address": None}
    fallbacks = {
        "condo": {"unit_sqft": 1150, "year_built": 2007, "bedrooms": 2},
        "commercial_sqft": None,
        "footprint": None,
    }
    s = _build_summary(condo_parcel, None, [], [], None, building_fallbacks=fallbacks)
    assert s.bldg_sqft == 1150 and s.bldg_sqft_source == "condo_unit"
    assert s.year_built == 2007
    assert s.bedrooms == 2


def test_build_summary_energy_benchmark_merge():
    """Large building (no chars, no commercial row): GFA + year built fill from
    energy benchmarking with its own provenance; the full benchmark rides
    PropertySummary.energy; footprints stay the last resort."""
    parcel = {"pin14": "14211000010000", "bldg_class": "599", "address": None}
    fallbacks = {
        "condo": None,
        "commercial_sqft": None,
        "energy": {
            "chicago_energy_rating": 3.5, "energy_star_score": 74,
            "gross_floor_area": 249095, "year_built": 1927,
            "primary_property_type": "Multifamily Housing", "site_eui": 88.5,
            "ghg_intensity": 5.8, "data_year": 2022, "not_submitted": False,
        },
        "footprint": {"stories": 21, "year_built": 1930, "bldg_sqft": 999},
    }
    s = _build_summary(parcel, None, [], [], None, building_fallbacks=fallbacks)
    assert s.bldg_sqft == 249095 and s.bldg_sqft_source == "energy_benchmark"
    # year_built is deliberately NOT filled from energy (owner-typed, wrong on
    # historic buildings) — the footprint fallback still supplies it.
    assert s.year_built == 1930 and s.year_built_source == "footprint"
    assert s.stories == 21.0 and s.stories_source == "footprint"
    assert s.energy is not None
    assert s.energy.chicago_energy_rating == 3.5
    assert s.energy.energy_star_score == 74

    # Commercial valuation (assessor-adjacent) still outranks energy GFA.
    fallbacks2 = dict(fallbacks, commercial_sqft=200000)
    s2 = _build_summary(parcel, None, [], [], None, building_fallbacks=fallbacks2)
    assert s2.bldg_sqft == 200000 and s2.bldg_sqft_source == "commercial_valuation"
    assert s2.energy is not None  # opex facts surface regardless of fill


def test_decode_units_words_and_single_family():
    from backend.retrieval.property import _decode_units
    assert _decode_units({"char_apts": "Two"}) == 2
    assert _decode_units({"char_apts": "Six"}) == 6
    # "None" (literal dataset string) + confirmed single-family -> 1 dwelling unit
    assert _decode_units({"char_apts": "None", "char_use": "Single-Family"}) == 1
    # Multi-family without an apartment count stays unknown
    assert _decode_units({"char_apts": "None", "char_use": "Multi-Family"}) is None
    assert _decode_units({}) is None
    # Legacy numeric strings (pre-decode vintages) don't decode — None over wrong
    assert _decode_units({"char_apts": "2"}) is None


@pytest.mark.asyncio
async def test_development_feasibility_skips_assessments_and_sales():
    """workflow=development_feasibility should only fetch characteristics."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.return_value = SAMPLE_CHARS
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, workflow="development_feasibility", client=client)

        assert result is not None
        assert result.pin14 == "14241020170000"
        assert result.bldg_sqft == 2600
        mock_chars.assert_awaited_once()
        mock_assess.assert_not_awaited()
        mock_sales.assert_not_awaited()
        assert result.assessment_history == []
        assert result.sales_history == []


@pytest.mark.asyncio
async def test_general_workflow_fetches_everything():
    """workflow=general (default) should fetch all sub-queries."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.return_value = SAMPLE_CHARS
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, workflow="general", client=client)

        assert result is not None
        mock_chars.assert_awaited_once()
        mock_assess.assert_awaited_once()
        mock_sales.assert_awaited_once()
        assert len(result.assessment_history) == 2
        assert len(result.sales_history) == 2


def test_build_summary_assessment_fallback_values():
    """Assessment should fall back from mailed to certified to board values."""
    parcel = {"pin14": "12345678901234", "address": "TEST"}
    assessments = [
        {"tax_year": "2024", "certified_tot": "40000"},
        {"tax_year": "2023", "board_tot": "38000"},
    ]
    summary = _build_summary(parcel, None, assessments, [])
    assert summary.assessment_history[0].total == 40000.0
    assert summary.assessment_history[1].total == 38000.0
    assert summary.total_assessed_value == 40000.0


def test_build_summary_skips_valueless_latest_year():
    """The CCAO's in-progress year (e.g. 2026) returns with NULL value columns
    omitted by Socrata. The headline value must come from the latest year that
    actually carries a value, and the valueless row must not pollute history.

    Mirrors the live shape verified against dataset uzyt-m557 (2026-06-14):
    the 2026 row has only {pin, year, class, township...}, no value columns.
    """
    parcel = {"pin14": "14331030110000", "address": "642 W BELDEN AVE"}
    assessments = [
        # latest year — valueless (class present, no value columns)
        {"year": "2026", "class": "205"},
        {"year": "2025", "mailed_tot": "114600", "mailed_land": "51925",
         "mailed_bldg": "62675"},
        {"year": "2024", "mailed_tot": "135000"},
    ]
    summary = _build_summary(parcel, None, assessments, [])
    # Headline value is the latest year that actually carries a value.
    assert summary.total_assessed_value == 114600.0
    # The valueless 2026 row is dropped from history entirely.
    assert [r.year for r in summary.assessment_history] == [2025, 2024]
    assert summary.assessment_history[0].total == 114600.0
