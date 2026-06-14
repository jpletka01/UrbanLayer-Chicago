"""Index builder tests — pure derivations + assemble_parcel + a mocked-network build."""

from __future__ import annotations

import datetime

from shapely.geometry import Polygon

from backend.discovery import index_build as ib
from backend.discovery.index_build import (
    _is_vacant,
    _land_use,
    _recency_days,
    _zoning_group,
    assemble_parcel,
)
from backend.discovery.parcel_index import read_index

AS_OF = datetime.date(2025, 1, 1)


def _box_around(lat: float, lon: float) -> Polygon:
    return Polygon([(lon - 0.01, lat - 0.01), (lon + 0.01, lat - 0.01),
                    (lon + 0.01, lat + 0.01), (lon - 0.01, lat + 0.01)])


# --- pure derivations -------------------------------------------------------


def test_land_use_by_class_prefix():
    assert _land_use("100") == "vacant"
    assert _land_use("299") == "residential"
    assert _land_use("311") == "multi_family"
    assert _land_use("517") == "commercial"
    assert _land_use("650") == "industrial"
    assert _land_use("000") == "exempt"
    assert _land_use("999") is None  # unmapped prefix


def test_is_vacant():
    assert _is_vacant("100") is True
    assert _is_vacant("299") is False


def test_zoning_group():
    assert _zoning_group("RM-5") == "residential"
    assert _zoning_group("B2-3") == "business"
    assert _zoning_group("C1-2") == "commercial"
    assert _zoning_group("M1-2") == "manufacturing"
    assert _zoning_group("DC-16") == "downtown"
    assert _zoning_group("PD 123") == "planned_development"
    assert _zoning_group("PMD 11") == "manufacturing"
    assert _zoning_group("POS-1") is None


def test_recency_days():
    assert _recency_days("2024-01-01", AS_OF) == 366  # 2024 is a leap year
    assert _recency_days("2024-01-01T00:00:00.000", AS_OF) == 366
    assert _recency_days(None, AS_OF) is None
    assert _recency_days("garbage", AS_OF) is None


# --- assemble_parcel --------------------------------------------------------


def test_assemble_full_parcel():
    lat, lon = 41.9, -87.7
    spine = {"pin": "14-31-100-001-0000", "class": "299", "lat": lat, "lon": lon}
    chars = {"char_land_sf": "5000", "char_bldg_sf": "2000", "char_yrblt": "1995", "char_apts": "3"}
    assess = {"mailed_tot": "250000", "mailed_bldg": "180000", "mailed_land": "70000"}
    sale = {"sale_price": "400000", "sale_date": "2024-01-01"}

    pin, out_lat, out_lon, attrs, regions = assemble_parcel(
        spine, chars, assess, sale,
        zoning_polys=[("RM-5", _box_around(lat, lon))],
        tif_polys=[_box_around(lat, lon)],
        ez_polys=[],
        neighborhood_ca=24,
        as_of=AS_OF,
    )

    assert pin == "14-31-100-001-0000"
    assert (out_lat, out_lon) == (lat, lon)
    assert attrs["land_use_class"] == "residential"
    assert attrs["is_vacant"] is False
    assert attrs["land_sqft"] == 5000.0
    assert attrs["bldg_sqft"] == 2000.0
    assert attrs["year_built"] == 1995
    assert attrs["units"] == 3
    assert attrs["total_assessed_value"] == 250000.0
    assert attrs["improvement_ratio"] == 2.5714  # 180000/70000
    assert attrs["last_sale_price"] == 400000.0
    assert attrs["sale_recency_days"] == 366
    assert attrs["price_per_sf"] == 200.0
    assert attrs["in_tif_district"] is True
    assert attrs["in_enterprise_zone"] is False
    assert attrs["zoning_group"] == "residential"
    assert attrs["density_band"] == 2.0  # RM-5 FAR
    assert regions == ["neighborhood:24"]


def test_assemble_minimal_parcel_no_joins_no_layers():
    lat, lon = 41.0, -88.0
    spine = {"pin": "p-vacant", "class": "100", "lat": lat, "lon": lon}
    _, _, _, attrs, regions = assemble_parcel(
        spine, None, None, None,
        zoning_polys=[], tif_polys=[], ez_polys=[], neighborhood_ca=24, as_of=AS_OF,
    )
    assert attrs["land_use_class"] == "vacant"
    assert attrs["is_vacant"] is True
    assert attrs["in_tif_district"] is False
    assert "zoning_group" not in attrs  # no polygon contained the point
    assert "land_sqft" not in attrs     # no characteristics row
    assert regions == ["neighborhood:24"]


# --- build_index (network mocked) -------------------------------------------


async def test_build_index_writes_loadable_index(tmp_path, monkeypatch):
    lat, lon = 41.9, -87.7
    box = _box_around(lat, lon)

    async def fake_tif(*a, **k):
        return [("TIF One", {}, box, {})]

    async def fake_ez(*a, **k):
        return []

    async def fake_spine(ca, *, client=None):
        return [{"pin": "14-31-100-001-0000", "pin_digits": "14311000010000",
                 "class": "311", "lat": lat, "lon": lon}]

    async def fake_batch(dataset, pins, order_field, client, settings):
        return {}  # no joins in this test

    async def fake_zoning(ca, *, client=None):
        return {"features": []}

    monkeypatch.setattr(ib, "_load_tif_boundaries", fake_tif)
    monkeypatch.setattr(ib, "_load_ez_boundaries", fake_ez)
    monkeypatch.setattr(ib, "_fetch_spine", fake_spine)
    monkeypatch.setattr(ib, "_batch_latest", fake_batch)
    monkeypatch.setattr(ib, "zoning_polygons_for_map", fake_zoning)
    monkeypatch.setattr(ib, "community_area_by_point", lambda lat, lon: 24)
    monkeypatch.setattr(ib, "default_index_path", lambda: tmp_path / "idx.db")

    data_version, total = await ib.build_index([24], as_of=AS_OF)
    assert total == 1
    assert data_version.startswith("idx-20250101-")

    version, parcels = read_index(tmp_path / "idx.db")
    assert version == data_version
    assert len(parcels) == 1
    p = parcels[0]
    assert p.get("land_use_class") == "multi_family"  # class 311
    assert p.get("in_tif_district") is True            # inside the mocked TIF polygon
    assert p.in_region("neighborhood:24")


async def test_build_index_degrades_when_a_layer_fails(tmp_path, monkeypatch):
    """A transient layer failure leaves its flag False instead of aborting the build."""
    async def boom(*a, **k):
        raise RuntimeError("503 Service Temporarily Unavailable")

    async def fake_ez(*a, **k):
        return []

    async def fake_spine(ca, *, client=None):
        return [{"pin": "p1", "pin_digits": "14311000010000", "class": "311",
                 "lat": 41.9, "lon": -87.7}]

    async def fake_batch(dataset, pins, order_field, client, settings):
        return {}

    async def fake_zoning(ca, *, client=None):
        return {"features": []}

    monkeypatch.setattr(ib, "_load_tif_boundaries", boom)  # TIF portal down
    monkeypatch.setattr(ib, "_load_ez_boundaries", fake_ez)
    monkeypatch.setattr(ib, "_fetch_spine", fake_spine)
    monkeypatch.setattr(ib, "_batch_latest", fake_batch)
    monkeypatch.setattr(ib, "zoning_polygons_for_map", fake_zoning)
    monkeypatch.setattr(ib, "community_area_by_point", lambda lat, lon: 24)
    monkeypatch.setattr(ib, "default_index_path", lambda: tmp_path / "idx.db")

    data_version, total = await ib.build_index([24], as_of=AS_OF)
    assert total == 1  # build did not abort
    _, parcels = read_index(tmp_path / "idx.db")
    assert parcels[0].get("in_tif_district") is False  # flag degraded, not crashed


def test_ensure_loaded_reads_built_index(tmp_path, monkeypatch):
    """Loader wiring: a built index becomes the current snapshot the evaluator reads."""
    from backend.discovery import parcel_source
    from backend.discovery.cqs import CQS, FilterAssignment, FlagPredicate, SortSpec
    from backend.discovery.evaluator import evaluate
    from backend.discovery.parcel_index import write_index

    path = tmp_path / "idx.db"
    write_index(path, data_version="idx-load-1", built_at=1, community_areas=[24],
                rows=[("p1", 41.9, -87.7, {"in_tif_district": True}, ["neighborhood:24"])])

    monkeypatch.setattr(parcel_source, "default_index_path", lambda: path)
    parcel_source._current_version = None
    parcel_source.default_source.clear()
    try:
        parcel_source.ensure_loaded()
        assert parcel_source.current_version() == "idx-load-1"
        cqs = CQS(
            filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))},
            sort=SortSpec(key="pin", dir="asc"),
        )
        assert evaluate(cqs, "idx-load-1").pins == ["p1"]
    finally:
        parcel_source._current_version = None
        parcel_source.default_source.clear()
