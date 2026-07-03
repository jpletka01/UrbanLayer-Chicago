"""Tests for geometry-derived parcel land area (backend/retrieval/property/parcel_geometry.py)."""

import math

import aiosqlite
import pytest
from unittest.mock import patch

from backend.retrieval.property.parcel_geometry import (
    _polygon_area_sqft,
    close,
    get_parcel_geometry_facts,
)


def _square_wkt(lat0: float, lon0: float, side_m: float) -> str:
    """WKT square of side_m meters centered near (lat0, lon0)."""
    dlat = side_m / 111_132.95
    dlon = side_m / (111_319.49 * math.cos(math.radians(lat0)))
    pts = [
        (lon0, lat0),
        (lon0 + dlon, lat0),
        (lon0 + dlon, lat0 + dlat),
        (lon0, lat0 + dlat),
        (lon0, lat0),
    ]
    coords = ", ".join(f"{x:.10f} {y:.10f}" for x, y in pts)
    return f"POLYGON (({coords}))"


def test_area_of_known_square_within_tolerance():
    # 30m x 30m at Chicago latitude = 900 m^2 = 9687.5 sqft
    wkt = _square_wkt(41.88, -87.63, 30.0)
    parsed = _polygon_area_sqft(wkt)
    assert parsed is not None
    area, geojson = parsed
    assert abs(area - 900 * 10.763910) / (900 * 10.763910) < 0.005
    assert geojson["type"] == "Polygon"


def test_area_rejects_garbage_and_empty():
    assert _polygon_area_sqft("not wkt at all") is None
    assert _polygon_area_sqft("POLYGON EMPTY") is None


@pytest.fixture
async def geometry_db(tmp_path):
    await close()
    db_path = tmp_path / "ptaxsim_geo.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute(
            "CREATE TABLE pin_geometry_raw ("
            " pin10 varchar(10), start_year int, end_year int,"
            " longitude double, latitude double, geometry TEXT,"
            " PRIMARY KEY (pin10, start_year))"
        )
        old = _square_wkt(41.88, -87.63, 20.0)
        new = _square_wkt(41.88, -87.63, 30.0)
        await conn.execute(
            "INSERT INTO pin_geometry_raw VALUES ('1431332018', 2000, 2015, -87.63, 41.88, ?)",
            (old,),
        )
        await conn.execute(
            "INSERT INTO pin_geometry_raw VALUES ('1431332018', 2016, 2024, -87.63, 41.88, ?)",
            (new,),
        )
        await conn.commit()
    yield db_path
    await close()


@pytest.mark.asyncio
async def test_facts_use_most_recent_boundary(geometry_db):
    with patch("backend.retrieval.property.parcel_geometry.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = geometry_db

        facts = await get_parcel_geometry_facts("14313320180000")
        assert facts is not None
        # 30m square (the 2016-2024 row), not the 20m one
        expected = 900 * 10.763910
        assert abs(facts["land_sqft_geom"] - expected) / expected < 0.005
        assert facts["geom_year"] == 2024
        assert facts["parcel_geometry"]["type"] == "Polygon"


@pytest.mark.asyncio
async def test_facts_none_for_unknown_pin(geometry_db):
    with patch("backend.retrieval.property.parcel_geometry.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = geometry_db

        assert await get_parcel_geometry_facts("99999999990000") is None


@pytest.mark.asyncio
async def test_facts_none_when_db_missing(tmp_path):
    await close()
    with patch("backend.retrieval.property.parcel_geometry.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = tmp_path / "nope.db"

        assert await get_parcel_geometry_facts("14313320180000") is None
