"""GET /api/capacity-map (WS8 Phase 1, decision Item 39): neighbors from a fixture index, polygons from a fixture
ptaxsim, a fixture zoning quilt and a fixture Commercial Valuation artifact.  No network."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend import capacity_map as cm
from backend.config import get_settings
from backend.discovery import parcel_source
from backend.discovery.parcel import default_source
from backend.discovery.parcel_index import IndexedParcel, IndexMeta
from backend.main import app
from backend.retrieval.property import commercial_artifact as ca
from ingestion import build_commercial_bldg_artifact as builder

LAT, LON = 41.9000, -87.6800
STEP = 0.0003  # each fixture lot is a 0.0002-degree square on a 0.0003 grid (about 4,000 sq ft)
VERSION = "capmap-test-v1"


def _lot(i: int) -> tuple[float, float, float, float]:
    x0, y0 = LON + i * STEP, LAT
    return x0, y0, x0 + 0.0002, y0 + 0.0002


def _pin(i: int, suffix: str = "0000") -> str:
    return f"17-09-100-{i:03d}-{suffix}"


def _attrs(**kw):
    base = {"class": "2-11", "land_sqft": 4000.0, "bldg_sqft": 4000.0, "address": "1 TEST ST"}
    base.update(kw)
    return base


# Lot i -> (attrs of the base row, extra PIN14 rows)
LOTS = {
    0: (_attrs(), []),  # FAR 1.0 against RT-4's 1.2: computable
    1: (_attrs(bldg_sqft=None, **{"class": "5-17"}), []),  # single-PIN commercial unit in the artifact: computable
    2: (_attrs(bldg_sqft=None, **{"class": "5-17"}), []),  # member of a 2-lot complex: multi_pin_member
    3: (_attrs(bldg_sqft=None, **{"class": "5-17"}), []),  # the complex's other lot
    4: (_attrs(), [("1001", {"class": "2-99"})]),  # condo building
    5: (_attrs(bldg_sqft=4000.0 * 1.2 * 3 + 500), []),  # apparently overbuilt
    6: (_attrs(), []),  # straddles RT-4 and B3-2 almost evenly: split_zoning
    7: (_attrs(), []),  # mostly B3-2 (80%): computable at low confidence
    8: (_attrs(bldg_sqft=None), []),  # no area anywhere: unknown_gfa
}


def _zoning():
    """RT-4 west of lot 6's middle, B3-2 east of it; lot 7 is placed 80/20."""
    x6 = _lot(6)[0] + 0.0001  # lot 6 split in half
    x7 = _lot(7)[0] + 0.00004  # lot 7: 20% RT-4, 80% B3-2
    west = box(LON - 0.01, LAT - 0.01, x6, LAT + 0.01)
    mid = box(x6, LAT - 0.01, _lot(7)[0], LAT + 0.01)
    east7 = box(_lot(7)[0], LAT - 0.01, x7, LAT + 0.01)
    east = box(x7, LAT - 0.01, LON + 0.02, LAT + 0.01)

    def f(geom, zone):
        from shapely.geometry import mapping

        return {"type": "Feature", "properties": {"ZONE_CLASS": zone}, "geometry": mapping(geom)}

    return {"type": "FeatureCollection", "features": [f(west, "RT-4"), f(mid, "B3-2"), f(east7, "RT-4"), f(east, "B3-2")]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    # Index
    parcels = []
    for i, (attrs, extra) in LOTS.items():
        x0, y0, x1, y1 = _lot(i)
        lat, lon = (y0 + y1) / 2, (x0 + x1) / 2
        parcels.append(IndexedParcel(_pin(i), lat, lon, attrs, ["neighborhood:24"]))
        for suffix, a in extra:
            parcels.append(IndexedParcel(_pin(i, suffix), lat, lon, a, ["neighborhood:24"]))
    parcel_source.set_snapshot(VERSION, parcels, meta=IndexMeta(VERSION, [24], [], 1_790_000_000))
    cm._grid = None
    cm._cache._store.clear()
    # ptaxsim
    db = tmp_path / "ptaxsim.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE pin_geometry_raw (pin10 varchar(10), start_year int, end_year int, longitude double, "
                "latitude double, geometry text, PRIMARY KEY (pin10, start_year, end_year))")
    for i in LOTS:
        g = box(*_lot(i))
        con.execute("INSERT INTO pin_geometry_raw VALUES (?,?,?,?,?,?)", (_pin(i).replace("-", "")[:10], 2006, 2024, 0, 0, g.wkt))
    # An older, different boundary for lot 0: the newest end_year must win.
    con.execute("INSERT INTO pin_geometry_raw VALUES (?,?,?,?,?,?)", (_pin(0).replace("-", "")[:10], 1999, 2005, 0, 0, box(0, 0, 1, 1).wkt))
    con.commit()
    con.close()
    monkeypatch.setattr(get_settings(), "ptaxsim_db_path", db)
    monkeypatch.setattr(get_settings(), "ptaxsim_enabled", True)
    # Commercial Valuation artifact
    art = tmp_path / "commercial_bldg_by_pin.json.gz"
    units = [
        [_pin(1).replace("-", ""), 3000, [_pin(1).replace("-", "")]],
        [_pin(2).replace("-", ""), 20000, [_pin(2).replace("-", ""), _pin(3).replace("-", "")]],
    ]
    builder.write({"assessor": {"year": "2024"}, "units": units}, {}, out=art, meta_out=tmp_path / "m.json")
    monkeypatch.setattr(ca, "ARTIFACT_PATH", art)
    ca._load.cache_clear()
    # Zoning quilt
    calls = {"n": 0, "fail": False}

    async def fake_zoning(lat, lon, *, radius_mi=0.25, client=None):
        calls["n"] += 1
        if calls["fail"]:
            raise RuntimeError("zoning layer down")
        return _zoning()

    monkeypatch.setattr("backend.retrieval.zoning.zoning_polygons_near", fake_zoning)
    yield {"client": TestClient(app), "calls": calls, "art": art}
    parcel_source._current_version = None
    parcel_source._current_meta = None
    default_source.clear()
    cm._grid = None
    cm._cache._store.clear()
    ca._load.cache_clear()


def _get(env, **params):
    params.setdefault("lat", LAT + 0.0001)
    params.setdefault("lon", LON + 4 * STEP)
    params.setdefault("radius_mi", 0.25)
    params = {k: v for k, v in params.items() if v is not None}
    r = env["client"].get("/api/capacity-map", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _by_pin(body):
    return {f["properties"]["pin10"]: f["properties"] for f in body["features"]["features"]}


def test_states_per_polygon(env):
    body = _get(env)
    p = _by_pin(body)
    s = {k[-3:]: v["state"] for k, v in p.items()}
    assert s == {
        "000": "computable", "001": "computable", "002": "multi_pin_member", "003": "multi_pin_member",
        "004": "condo_building", "005": "apparently_overbuilt", "006": "split_zoning", "007": "computable",
        "008": "unknown_gfa",
    }
    assert body["unchecked"] == []


def test_computable_values_and_sources(env):
    p = _by_pin(_get(env))
    lot0 = p["17-09-100-000"]
    assert lot0["zone_class"] == "RT-4" and lot0["allowed_far"] == 1.2
    assert lot0["existing_far"] == 1.0 and lot0["utilization"] == pytest.approx(0.833, abs=0.001)
    assert lot0["confidence"] == "standard" and lot0["inputs"]["bldg_sqft"]["source"] == cm.SOURCE_INDEX
    lot1 = p["17-09-100-001"]
    assert lot1["inputs"]["bldg_sqft"] == {"value": 3000.0, "source": cm.SOURCE_ARTIFACT}
    assert lot1["inputs"]["bldg_sqft_year"]["value"] == "2024"


def test_zoning_by_overlap_and_low_confidence_near_a_boundary(env):
    p = _by_pin(_get(env))
    lot7 = p["17-09-100-007"]
    assert lot7["zone_class"] == "B3-2" and lot7["inputs"]["zoning"]["share"] == pytest.approx(0.8, abs=0.01)
    assert lot7["confidence"] == "low" and lot7["reason"] == "district_boundary"
    assert p["17-09-100-006"]["utilization"] is None  # split: never colored


def test_complex_total_is_never_on_a_member_lot(env):
    p = _by_pin(_get(env))
    for k in ("17-09-100-002", "17-09-100-003"):
        assert p[k]["utilization"] is None and p[k]["existing_far"] is None
        assert p[k]["inputs"]["complex"]["complex_bldg_sqft"] == 20000.0


def test_overbuilt_and_unknown_are_never_colored(env):
    p = _by_pin(_get(env))
    for k in ("17-09-100-005", "17-09-100-008", "17-09-100-004"):
        assert p[k]["utilization"] is None and p[k]["confidence"] == "withheld"


def test_summary_counts_and_verdict(env):
    body = _get(env)
    summ = body["summary"]
    assert summ["polygons"] == 9 and summ["colorable"] == 3
    assert sum(summ["states"].values()) == summ["polygons"]
    assert summ["colorable_share"] == pytest.approx(3 / 9, abs=1e-4) and summ["verdict"] == "standard"
    prov = body["provenance"]["capacity.utilization"]
    assert prov["tier"] == "our_calculation" and prov["coverage"]["n"] == 3


def test_newest_boundary_wins(env):
    p = _by_pin(_get(env))
    assert p["17-09-100-000"]["geometry_year"] == 2024


def test_radius_is_clamped_and_filters_neighbors(env):
    body = _get(env, radius_mi=0.01)
    assert body["radius_mi"] == cm.MIN_RADIUS_MI
    assert _get(env, radius_mi=9)["radius_mi"] == cm.MAX_RADIUS_MI
    # 0.05 mile around lot 0 reaches lots 0-2 only (lot spacing is about 0.0155 mile)... and not lot 8.
    near = _by_pin(_get(env, lat=LAT + 0.0001, lon=LON + 0.0001, radius_mi=0.05))
    assert "17-09-100-000" in near and "17-09-100-008" not in near


def test_subject_by_pin(env):
    body = _get(env, pin="17-09-100-004-0000", lat=None, lon=None)
    p = _by_pin(body)
    assert p["17-09-100-004"]["subject"] is True and body["subject"]["pin10"] == "17-09-100-004"
    assert sum(1 for v in p.values() if v["subject"]) == 1
    assert _get(env, pin="1709100004", lat=None, lon=None)["subject"]["pin10"] == "17-09-100-004"


def test_subject_found_through_its_unit_pins_alone(env):
    """A condo building indexed only by unit PINs (no -0000 row) still locates the map (7141 N Kedzie on the panel)."""
    parcels = [p for p in default_source.get(VERSION) if p.pin != _pin(4)]
    parcel_source.set_snapshot(VERSION, parcels, meta=IndexMeta(VERSION, [24], [], 1_790_000_000))
    cm._grid = None
    body = _get(env, pin=_pin(4), lat=None, lon=None)
    assert body["subject"]["pin10"] == "17-09-100-004"
    assert _by_pin(body)["17-09-100-004"]["state"] == "condo_building"


def test_zoning_failure_is_unchecked_and_never_cached(env):
    env["calls"]["fail"] = True
    body = _get(env)
    assert body["unchecked"] == ["zoning"] and body["features"]["features"] == []
    assert body["summary"]["verdict"] == "unavailable"
    env["calls"]["fail"] = False
    assert _get(env)["unchecked"] == []  # recovered on the next call: the failure was not cached


def test_missing_artifact_marks_the_parcels_that_needed_it(env):
    env["art"].unlink()
    ca._load.cache_clear()
    body = _get(env)
    p = _by_pin(body)
    assert "commercial_valuation" in body["unchecked"]
    assert p["17-09-100-001"]["state"] == "unchecked"  # never "no building"
    assert p["17-09-100-000"]["state"] == "computable"  # the index's own area still counts
    ca._load.cache_clear()
    builder.write({"assessor": {"year": "2024"}, "units": []}, {}, out=env["art"], meta_out=env["art"].with_name("m.json"))
    assert "commercial_valuation" not in _get(env)["unchecked"]  # not cached


def test_ptaxsim_failure_is_unchecked(env, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "ptaxsim_db_path", tmp_path / "absent.db")
    body = _get(env)
    assert body["unchecked"] == ["parcel_geometry"] and body["features"]["features"] == []


def test_empty_index_is_unchecked(env):
    parcel_source.set_snapshot(parcel_source.EMPTY_VERSION, [], meta=None)
    assert _get(env)["unchecked"] == ["discovery_index"]


def test_withheld_view_carries_no_utilization():
    """A view under 10% colorable keeps its states but no utilization, so nothing can draw bins from it."""
    lot = box(0, 0, 0.0002, 0.0002)
    quilt = cm.ZoningQuilt({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ZONE_CLASS": "RT-4"}, "geometry": box(-1, -1, 1, 1).__geo_interface__}]})
    groups = [cm.Group(f"17-09-100-{i:03d}", ((f"17-09-100-{i:03d}-0000", _attrs(bldg_sqft=None if i else 4000.0)),), 0, 0)
              for i in range(11)]
    polygons = {g.pin10: (lot, 2024) for g in groups}
    fc, summary, _ = cm.assemble(groups, polygons, quilt, lambda pin: None, far_of=lambda z: 1.2)
    assert summary["colorable"] == 1 and summary["verdict"] == "withheld"
    assert all(f["properties"]["utilization"] is None for f in fc["features"])
    assert any(f["properties"]["state"] == "computable" for f in fc["features"])


def test_request_validation(env):
    c = env["client"]
    assert c.get("/api/capacity-map").status_code == 422
    assert c.get("/api/capacity-map", params={"pin": "12-34"}).status_code == 422


def test_open_space_district_is_not_outside_zoning():
    """POS and T districts have no zoning group in the index builder; on the map they are a known district with no
    FAR in the table, never "no zoning" (found on the panel: 182 POS-3 parcels at 12200 S Hoxie Ave)."""
    lot = box(0, 0, 0.0002, 0.0002)
    quilt = cm.ZoningQuilt({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ZONE_CLASS": "POS-3"}, "geometry": box(-1, -1, 1, 1).__geo_interface__}]})
    group = cm.Group("17-09-100-001", (("17-09-100-001-0000", _attrs()),), 0, 0)
    feat, _ = cm.polygon_feature(group, (lot, 2024), quilt, lambda pin: None, far_of=cm._far_of)
    assert feat["properties"]["zone_class"] == "POS-3" and feat["properties"]["state"] == "no_allowed_far"


def test_quilt_ignores_sliver_coverage():
    quilt = cm.ZoningQuilt({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ZONE_CLASS": "RS-3"}, "geometry": box(0, 0, 0.3, 1).__geo_interface__}]})
    ans = quilt.zone_of(box(0, 0, 1, 1))
    assert ans.zone_class is None  # 30% covered: outside zoning, not RS-3
