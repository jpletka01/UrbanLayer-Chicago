"""Tests for PDF Report v2 retrieval functions and extraction module."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.retrieval.buildings import (
    address_specific_permits,
    address_specific_violations,
    nearby_new_construction,
    parse_chicago_address,
)
from backend.retrieval.property.sales import nearby_comparable_sales, _haversine_mi
from backend.retrieval.zoning import adjacent_parcel_zoning
from backend.zoning_extract import calculate_development_potential, extract_zoning_standards
from backend.models import DevelopmentPotential, ZoningStandards


class TestParseChicagoAddress:
    def test_standard_format(self):
        result = parse_chicago_address("2400 N Milwaukee Ave")
        assert result == {"number": "2400", "direction": "N", "name": "MILWAUKEE"}

    def test_south_direction(self):
        result = parse_chicago_address("1234 S State St")
        assert result == {"number": "1234", "direction": "S", "name": "STATE"}

    def test_west_blvd(self):
        result = parse_chicago_address("5600 W Chicago Blvd")
        assert result == {"number": "5600", "direction": "W", "name": "CHICAGO"}

    def test_with_city_state(self):
        result = parse_chicago_address("2400 N MILWAUKEE AVE, Chicago, IL 60647")
        assert result == {"number": "2400", "direction": "N", "name": "MILWAUKEE"}

    def test_no_suffix(self):
        result = parse_chicago_address("100 E Grand")
        assert result == {"number": "100", "direction": "E", "name": "GRAND"}

    def test_no_suffix_with_city(self):
        result = parse_chicago_address("100 E GRAND, Chicago, IL")
        assert result == {"number": "100", "direction": "E", "name": "GRAND"}

    def test_invalid_address(self):
        assert parse_chicago_address("not an address") is None

    def test_missing_direction(self):
        assert parse_chicago_address("2400 Milwaukee Ave") is None


class TestHaversine:
    def test_same_point(self):
        assert _haversine_mi(41.9, -87.6, 41.9, -87.6) == 0.0

    def test_known_distance(self):
        # ~1 degree latitude ≈ 69 miles
        dist = _haversine_mi(41.0, -87.6, 42.0, -87.6)
        assert 68 < dist < 70


class TestAdjacentParcelZoning:
    @pytest.mark.asyncio
    async def test_returns_four_directions(self):
        with patch("backend.retrieval.zoning.lookup_zoning") as mock:
            mock.return_value = {"zone_class": "RS-3", "zone_type": 1}
            result = await adjacent_parcel_zoning(41.9, -87.7)
            assert set(result.keys()) == {"N", "S", "E", "W"}
            assert result["N"] == "RS-3"
            assert mock.call_count == 4

    @pytest.mark.asyncio
    async def test_handles_failure_gracefully(self):
        with patch("backend.retrieval.zoning.lookup_zoning") as mock:
            mock.side_effect = [
                {"zone_class": "B3-2"},
                Exception("timeout"),
                None,
                {"zone_class": "RS-3"},
            ]
            result = await adjacent_parcel_zoning(41.9, -87.7)
            assert result["N"] == "B3-2"
            assert result["S"] is None
            assert result["E"] is None
            assert result["W"] == "RS-3"


class TestNearbyComparableSales:
    @pytest.mark.asyncio
    async def test_empty_when_no_parcels(self):
        with patch("backend.retrieval.property.sales.socrata_get", new_callable=AsyncMock) as mock:
            mock.return_value = []
            result = await nearby_comparable_sales(41.9, -87.7, "2")
            assert result == {"summary": {}, "sales": []}

    @pytest.mark.asyncio
    async def test_builds_comps_from_data(self):
        parcels = [
            {"pin": "1234567890", "class": "211", "latitude": "41.901", "longitude": "-87.701"},
            {"pin": "9876543210", "class": "212", "latitude": "41.899", "longitude": "-87.699"},
        ]
        sales = [
            {"pin": "1234567890", "sale_date": "2025-01-15", "sale_price": "300000", "sale_deed_type": "WARRANTY", "class": "211"},
            {"pin": "9876543210", "sale_date": "2024-06-01", "sale_price": "250000", "sale_deed_type": "WARRANTY", "class": "212"},
        ]
        chars = [
            {"pin": "1234567890", "char_land_sf": "3000", "char_bldg_sf": "1500"},
            {"pin": "9876543210", "char_land_sf": "2500", "char_bldg_sf": "1200"},
        ]

        call_count = [0]
        async def mock_socrata(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return parcels
            elif call_count[0] == 2:
                return sales
            else:
                return chars

        with patch("backend.retrieval.property.sales.socrata_get", side_effect=mock_socrata):
            result = await nearby_comparable_sales(41.9, -87.7, "2")
            assert result["summary"]["sales_volume"] == 2
            assert result["summary"]["median_sale_price"] == 275000.0
            assert len(result["sales"]) == 2
            assert result["sales"][0]["pin"] == "1234567890"
            assert result["sales"][0]["price_per_land_sqft"] == 100.0
            assert result["sales"][0]["price_per_bldg_sqft"] == 200.0


class TestAddressSpecificPermits:
    @pytest.mark.asyncio
    async def test_queries_by_address(self):
        with patch("backend.retrieval.buildings.socrata_get", new_callable=AsyncMock) as mock:
            mock.return_value = [
                {"permit_type": "PERMIT - RENOVATION/ALTERATION", "issue_date": "2024-06-01"}
            ]
            result = await address_specific_permits("2400", "N", "MILWAUKEE")
            assert len(result) == 1
            assert result[0]["permit_type"] == "PERMIT - RENOVATION/ALTERATION"
            call_args = mock.call_args
            assert "street_number='2400'" in call_args[0][1]["$where"]


class TestAddressSpecificViolations:
    @pytest.mark.asyncio
    async def test_queries_by_address(self):
        with patch("backend.retrieval.buildings.socrata_get", new_callable=AsyncMock) as mock:
            mock.return_value = [
                {"violation_status": "OPEN", "violation_date": "2024-03-01"}
            ]
            result = await address_specific_violations("2400", "N", "MILWAUKEE")
            assert len(result) == 1
            assert result[0]["violation_status"] == "OPEN"


class TestNearbyNewConstruction:
    @pytest.mark.asyncio
    async def test_counts_come_from_aggregate_not_sample(self):
        """Counts + investment are TRUE area totals from the grouped aggregate,
        not tallies over the capped 20-row sample (which undercounted active
        corridors and mixed demolition costs into 'investment')."""
        totals = [
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "count": "37", "total_cost": "12500000"},
            {"permit_type": "PERMIT - WRECKING/DEMOLITION", "count": "9", "total_cost": "400000"},
        ]
        sample = [
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "issue_date": "2024-06-01"},
            {"permit_type": "PERMIT - WRECKING/DEMOLITION", "issue_date": "2024-04-01"},
        ]
        with patch("backend.retrieval.buildings.socrata_aggregate", new_callable=AsyncMock) as agg, \
             patch("backend.retrieval.buildings.socrata_get", new_callable=AsyncMock) as get:
            agg.return_value = totals
            get.return_value = sample
            result = await nearby_new_construction(41.9, -87.7)
            assert result["new_construction_count"] == 37   # not len(sample)
            assert result["demolition_count"] == 9
            # Demolition cost excluded from the investment figure.
            assert result["new_construction_cost"] == 12_500_000.0
            assert len(result["recent_projects"]) == 2


class TestCalculateDevelopmentPotential:
    def test_basic_calculation(self):
        standards = ZoningStandards(far=1.2, lot_coverage_pct=0.6)
        result = calculate_development_potential(standards, land_sqft=5000, bldg_sqft=2000)
        assert result.max_buildable_sqft == 6000
        assert result.development_surplus_sqft == 4000
        assert result.max_lot_coverage_sqft == 3000

    def test_no_far(self):
        standards = ZoningStandards(far=None)
        result = calculate_development_potential(standards, land_sqft=5000, bldg_sqft=2000)
        assert result.max_buildable_sqft is None
        assert result.development_surplus_sqft is None

    def test_zero_land(self):
        standards = ZoningStandards(far=1.5)
        result = calculate_development_potential(standards, land_sqft=0, bldg_sqft=0)
        assert result.max_buildable_sqft is None


class TestExtractZoningStandards:
    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        mock_chunks = [MagicMock(section_title="17-3-0400", text="FAR is 2.2 in B3-2")]

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(type="text", text='{"far": 2.2, "max_height_ft": 50, "extraction_confidence": "high", "permitted_uses": ["Retail"], "special_uses": [], "notes": []}')]

        with patch("backend.zoning_extract.semantic_search", new_callable=AsyncMock) as mock_search, \
             patch("backend.zoning_extract.tracked_create", new_callable=AsyncMock) as mock_create:
            mock_search.return_value = mock_chunks
            mock_create.return_value = mock_resp
            result = await extract_zoning_standards("B3-2")
            assert result is not None
            assert result.far == 2.2
            assert result.max_height_ft == 50
            assert result.extraction_confidence == "high"

    @pytest.mark.asyncio
    async def test_returns_none_on_search_failure(self):
        with patch("backend.zoning_extract.semantic_search", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("Qdrant down")
            result = await extract_zoning_standards("B3-2")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_bad_json(self):
        mock_chunks = [MagicMock(section_title="test", text="test")]
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(type="text", text="not json")]

        with patch("backend.zoning_extract.semantic_search", new_callable=AsyncMock) as mock_search, \
             patch("backend.zoning_extract.tracked_create", new_callable=AsyncMock) as mock_create:
            mock_search.return_value = mock_chunks
            mock_create.return_value = mock_resp
            result = await extract_zoning_standards("B3-2")
            assert result is None
