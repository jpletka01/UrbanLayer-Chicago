"""Tests for FAR-normalized comparable sales (property/comps_far.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property import comps_far
from backend.retrieval.property.comps_far import (
    QUILT_MAX_MI,
    QUILT_MIN_MI,
    annotate_far_normalized,
)

LAT, LON = 41.9105, -87.6773


def _square(lon, lat, half=0.001):
    """A small axis-aligned polygon around a point, as GeoJSON coordinates."""
    return [[
        [lon - half, lat - half], [lon + half, lat - half],
        [lon + half, lat + half], [lon - half, lat + half],
        [lon - half, lat - half],
    ]]


def _quilt(*zones):
    """zones: (zone_class, lon, lat) triples -> a GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ZONE_CLASS": z},
                "geometry": {"type": "Polygon", "coordinates": _square(lon, lat)},
            }
            for z, lon, lat in zones
        ],
    }


def _comp(pin, price, land, lon, lat, sale_type="LAND", dist=0.1):
    return {
        "pin": pin, "sale_price": price, "land_sqft": land,
        "lat": lat, "lon": lon, "sale_type": sale_type, "distance_mi": dist,
    }


def _patch_quilt(fc):
    return patch(
        "backend.retrieval.property.comps_far.zoning_polygons_near",
        new=AsyncMock(return_value=fc),
    )


@pytest.mark.asyncio
async def test_normalizes_price_by_land_area_and_far():
    # B3-2 has FAR 2.2 in the Title-17 table.
    comps = {"summary": {}, "sales": [_comp("A", 1_100_000, 5000, LON, LAT)]}
    with _patch_quilt(_quilt(("B3-2", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)

    sale = out["sales"][0]
    assert sale["zone_class"] == "B3-2"
    assert sale["far"] == 2.2
    # 1,100,000 / (5000 * 2.2) = 100.0
    assert sale["price_per_buildable_sqft"] == 100.0


@pytest.mark.asyncio
async def test_same_price_per_land_foot_differs_once_density_is_applied():
    """The whole point: equal $/land-ft is not equal value at different FAR."""
    dense_lon, sparse_lon = LON, LON + 0.01
    comps = {"summary": {}, "sales": [
        _comp("dense", 500_000, 5000, dense_lon, LAT),    # $100/land ft, FAR 2.2
        _comp("sparse", 500_000, 5000, sparse_lon, LAT),  # $100/land ft, FAR 0.9
    ]}
    with _patch_quilt(_quilt(("B3-2", dense_lon, LAT), ("RS-3", sparse_lon, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)

    dense, sparse = out["sales"]
    assert dense["price_per_buildable_sqft"] < sparse["price_per_buildable_sqft"], (
        "the higher-FAR lot must price LOWER per buildable foot at equal land price"
    )


@pytest.mark.asyncio
async def test_median_prefers_a_clean_land_only_basis():
    comps = {"summary": {}, "sales": [
        _comp("l1", 440_000, 1000, LON, LAT, sale_type="LAND"),          # 200/bf
        _comp("l2", 220_000, 1000, LON, LAT, sale_type="LAND"),          # 100/bf
        _comp("b1", 4_400_000, 1000, LON, LAT, sale_type="LAND AND BUILDING"),
    ]}
    with _patch_quilt(_quilt(("B3-2", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)

    s = out["summary"]
    assert s["buildable_median_basis"] == "land_only"
    assert s["buildable_median_n"] == 2
    assert s["median_price_per_buildable_sqft"] == 150.0  # median(200, 100)


@pytest.mark.asyncio
async def test_median_falls_back_to_mixed_and_says_so():
    """No vacant-land comps: still useful, but the basis must be disclosed."""
    comps = {"summary": {}, "sales": [
        _comp("b1", 440_000, 1000, LON, LAT, sale_type="LAND AND BUILDING"),
        _comp("b2", 220_000, 1000, LON, LAT, sale_type=None),
    ]}
    with _patch_quilt(_quilt(("B3-2", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)

    s = out["summary"]
    assert s["buildable_median_basis"] == "mixed"
    assert s["buildable_median_n"] == 2
    assert s["median_price_per_buildable_sqft"] == 150.0


@pytest.mark.asyncio
async def test_zone_without_a_published_far_is_left_unnormalized():
    """PDs publish no FAR — that is a gap, not a zero."""
    comps = {"summary": {}, "sales": [_comp("pd", 1_000_000, 5000, LON, LAT)]}
    with _patch_quilt(_quilt(("PD 835", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)

    sale = out["sales"][0]
    assert sale.get("price_per_buildable_sqft") is None
    assert "median_price_per_buildable_sqft" not in out["summary"]


@pytest.mark.asyncio
async def test_comp_outside_the_quilt_is_skipped():
    comps = {"summary": {}, "sales": [_comp("far_away", 500_000, 5000, LON + 5, LAT)]}
    with _patch_quilt(_quilt(("B3-2", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)
    assert out["sales"][0].get("zone_class") is None


@pytest.mark.asyncio
async def test_comp_without_coordinates_is_skipped():
    comps = {"summary": {}, "sales": [_comp("nocoord", 500_000, 5000, 0, 0)]}
    with _patch_quilt(_quilt(("B3-2", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)
    assert out["sales"][0].get("price_per_buildable_sqft") is None


@pytest.mark.asyncio
async def test_missing_price_or_land_area_yields_no_metric():
    comps = {"summary": {}, "sales": [
        _comp("nolan", 500_000, None, LON, LAT),
        _comp("noprice", None, 5000, LON, LAT),
        _comp("zeroland", 500_000, 0, LON, LAT),
    ]}
    with _patch_quilt(_quilt(("B3-2", LON, LAT))):
        out = await annotate_far_normalized(comps, LAT, LON)

    for sale in out["sales"]:
        assert sale.get("price_per_buildable_sqft") is None
        # The zone/FAR still resolve — only the ratio is unavailable.
        assert sale["zone_class"] == "B3-2"
    assert "median_price_per_buildable_sqft" not in out["summary"]


@pytest.mark.asyncio
async def test_a_failed_quilt_degrades_quietly():
    comps = {"summary": {}, "sales": [_comp("A", 500_000, 5000, LON, LAT)]}
    with patch(
        "backend.retrieval.property.comps_far.zoning_polygons_near",
        new=AsyncMock(side_effect=RuntimeError("arcgis down")),
    ):
        out = await annotate_far_normalized(comps, LAT, LON)
    assert out["sales"][0].get("price_per_buildable_sqft") is None
    assert out["summary"] == {}


@pytest.mark.asyncio
async def test_empty_quilt_is_not_an_error():
    comps = {"summary": {}, "sales": [_comp("A", 500_000, 5000, LON, LAT)]}
    with _patch_quilt({"type": "FeatureCollection", "features": []}):
        out = await annotate_far_normalized(comps, LAT, LON)
    assert out["sales"][0].get("zone_class") is None


@pytest.mark.asyncio
async def test_no_comps_short_circuits_without_fetching():
    mock = AsyncMock(return_value=_quilt(("B3-2", LON, LAT)))
    with patch("backend.retrieval.property.comps_far.zoning_polygons_near", new=mock):
        out = await annotate_far_normalized({"summary": {}, "sales": []}, LAT, LON)
    assert mock.await_count == 0
    assert out["sales"] == []


class TestQuiltRadius:
    """The quilt must cover the comps — they reach ~0.55 mi once the search widens."""

    def test_sized_from_the_furthest_comp(self):
        sales = [{"distance_mi": 0.5}, {"distance_mi": 0.2}]
        assert comps_far._quilt_radius_mi(sales) == pytest.approx(0.6)

    def test_floors_at_the_minimum(self):
        assert comps_far._quilt_radius_mi([{"distance_mi": 0.01}]) == QUILT_MIN_MI

    def test_caps_so_one_stray_comp_cannot_demand_a_huge_envelope(self):
        assert comps_far._quilt_radius_mi([{"distance_mi": 40.0}]) == QUILT_MAX_MI

    def test_defaults_when_no_distances_are_known(self):
        assert comps_far._quilt_radius_mi([{"pin": "x"}]) == QUILT_MIN_MI


class TestLandAreaBackfill:
    """CCAO characteristics is residential-only, so most comps arrive with no land
    area — the metric is dead without this fill."""

    @staticmethod
    def _facts(area):
        return {"land_sqft_geom": area, "parcel_geometry": {}, "geom_year": 2024}

    @pytest.mark.asyncio
    async def test_fills_a_null_land_area_from_parcel_geometry(self):
        comps = {"summary": {}, "sales": [
            dict(_comp("17061070320000", 1_100_000, None, LON, LAT), land_sqft=None),
        ]}
        with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
             patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts",
                   new=AsyncMock(return_value=self._facts(5000))):
            out = await annotate_far_normalized(comps, LAT, LON)

        sale = out["sales"][0]
        assert sale["land_sqft"] == 5000
        assert sale["land_sqft_source"] == "geometry"
        assert sale["price_per_buildable_sqft"] == 100.0  # 1.1M / (5000 * 2.2)

    @pytest.mark.asyncio
    async def test_never_overwrites_an_existing_land_area(self):
        comps = {"summary": {}, "sales": [_comp("17061070320000", 1_100_000, 5000, LON, LAT)]}
        mock = AsyncMock(return_value=self._facts(99999))
        with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
             patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts", new=mock):
            out = await annotate_far_normalized(comps, LAT, LON)

        assert out["sales"][0]["land_sqft"] == 5000
        assert "land_sqft_source" not in out["sales"][0]
        assert mock.await_count == 0

    @pytest.mark.asyncio
    async def test_skips_condo_unit_pins(self):
        """A unit-PIN shares the building footprint — filling it would hand every
        unit the whole lot and badly understate price per buildable foot."""
        comps = {"summary": {}, "sales": [
            dict(_comp("17061070321005", 300_000, None, LON, LAT), land_sqft=None),
        ]}
        mock = AsyncMock(return_value=self._facts(5000))
        with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
             patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts", new=mock):
            out = await annotate_far_normalized(comps, LAT, LON)

        assert mock.await_count == 0, "unit-PINs must not be filled"
        assert out["sales"][0].get("land_sqft") is None
        assert out["sales"][0].get("price_per_buildable_sqft") is None

    @pytest.mark.asyncio
    async def test_survives_a_geometry_lookup_failure(self):
        comps = {"summary": {}, "sales": [
            dict(_comp("17061070320000", 1_100_000, None, LON, LAT), land_sqft=None),
        ]}
        with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
             patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts",
                   new=AsyncMock(side_effect=RuntimeError("ptaxsim missing"))):
            out = await annotate_far_normalized(comps, LAT, LON)
        assert out["sales"][0].get("price_per_buildable_sqft") is None

    @pytest.mark.asyncio
    async def test_no_geometry_row_leaves_the_comp_alone(self):
        comps = {"summary": {}, "sales": [
            dict(_comp("17061070320000", 1_100_000, None, LON, LAT), land_sqft=None),
        ]}
        with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
             patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts",
                   new=AsyncMock(return_value=None)):
            out = await annotate_far_normalized(comps, LAT, LON)
        assert out["sales"][0].get("land_sqft") is None


@pytest.mark.asyncio
async def test_does_not_mutate_the_callers_cached_comps():
    """`nearby_comparable_sales` returns a CACHED dict.

    Annotating it in place leaked back into that cache: the next request found
    land_sqft already filled, so the fill never ran and `land_sqft_source` came back
    None for a value that WAS geometry-derived — the same parcel reporting different
    provenance on a cache hit than on a miss.
    """
    original = {
        "summary": {"median_sale_price": 500_000},
        "sales": [dict(_comp("17061070320000", 1_100_000, None, LON, LAT), land_sqft=None)],
    }
    with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
         patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts",
               new=AsyncMock(return_value={"land_sqft_geom": 5000})):
        out = await annotate_far_normalized(original, LAT, LON)

    # The caller's object is untouched...
    assert original["sales"][0]["land_sqft"] is None
    assert "price_per_buildable_sqft" not in original["sales"][0]
    assert "median_price_per_buildable_sqft" not in original["summary"]
    assert original["summary"]["median_sale_price"] == 500_000
    # ...and the returned copy carries the annotations.
    assert out["sales"][0]["land_sqft"] == 5000
    assert out["sales"][0]["land_sqft_source"] == "geometry"
    assert out["summary"]["median_price_per_buildable_sqft"] == 100.0
    assert out["summary"]["median_sale_price"] == 500_000


@pytest.mark.asyncio
async def test_repeated_annotation_is_stable():
    """Two calls over the same cached input must agree, provenance included."""
    cached = {
        "summary": {},
        "sales": [dict(_comp("17061070320000", 1_100_000, None, LON, LAT), land_sqft=None)],
    }
    with _patch_quilt(_quilt(("B3-2", LON, LAT))), \
         patch("backend.retrieval.property.comps_far.get_parcel_geometry_facts",
               new=AsyncMock(return_value={"land_sqft_geom": 5000})):
        first = await annotate_far_normalized(cached, LAT, LON)
        second = await annotate_far_normalized(cached, LAT, LON)

    assert first["sales"][0] == second["sales"][0]
    assert first["summary"] == second["summary"]
    assert second["sales"][0]["land_sqft_source"] == "geometry"
