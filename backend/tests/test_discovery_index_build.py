"""Index builder tests — pure derivations + assemble_parcel + a mocked-network build."""

from __future__ import annotations

import datetime

from shapely.geometry import Polygon

from backend.discovery import index_build as ib
from backend.discovery.index_build import (
    _compute_value_percentile,
    _is_vacant,
    _land_use,
    _nearest_rail_mi,
    _populated_fields,
    _recency_days,
    _recipe_counts,
    _zoning_group,
    assemble_parcel,
)
from backend.discovery.parcel_index import read_index, read_meta

AS_OF = datetime.date(2025, 1, 1)

# A CTA rail station ~0.5 mi north of the test parcels at (41.9, -87.7).
_RAIL = [(41.9072, -87.7)]


def _assemble(spine, chars=None, assess=None, sale=None, **kw):
    """Helper: assemble_parcel with sensible defaults for the new keyword args."""
    kw.setdefault("zoning_polys", [])
    kw.setdefault("tif_polys", [])
    kw.setdefault("ez_polys", [])
    kw.setdefault("rail_stations", [])
    kw.setdefault("neighborhood_ca", 24)
    kw.setdefault("as_of", AS_OF)
    return assemble_parcel(spine, chars, assess, sale, **kw)


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
        rail_stations=_RAIL,
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
    assert attrs["improvement_ratio"] == 2.5714  # 180000/70000 (shipped field: building-to-land)
    assert attrs["last_sale_price"] == 400000.0
    assert attrs["sale_recency_days"] == 366
    assert attrs["price_per_sf"] == 200.0
    assert attrs["in_tif_district"] is True
    assert attrs["in_enterprise_zone"] is False
    assert attrs["zoning_group"] == "residential"
    assert attrs["density_band"] == 2.0  # RM-5 FAR
    # Derived fields. imp_share = 180000/250000 = 0.72 (land_share 0.28); not a teardown.
    assert attrs["is_teardown_candidate"] is False
    # built_FAR = 2000/5000 = 0.4; FAR_headroom = (2.0-0.4)/2.0 = 0.8;
    # upside = round(100 * (0.6*0.8 + 0.4*0.28)) = round(59.2) = 59
    assert attrs["upside_score"] == 59
    assert 0.45 < attrs["cta_rail_distance_mi"] < 0.55  # station ~0.5 mi away
    assert regions == ["neighborhood:24"]


def test_assemble_minimal_parcel_no_joins_no_layers():
    lat, lon = 41.0, -88.0
    spine = {"pin": "p-vacant", "class": "100", "lat": lat, "lon": lon}
    _, _, _, attrs, regions = _assemble(spine)
    assert attrs["land_use_class"] == "vacant"
    assert attrs["is_vacant"] is True
    assert attrs["in_tif_district"] is False
    assert "zoning_group" not in attrs  # no polygon contained the point
    assert "land_sqft" not in attrs     # no characteristics row
    # Derived fields stay absent (NULL) when their inputs are missing.
    assert "is_teardown_candidate" not in attrs  # no assessment / sizes
    assert "upside_score" not in attrs           # no zoning / sizes
    assert "cta_rail_distance_mi" not in attrs    # empty station list
    assert regions == ["neighborhood:24"]


def test_nearest_rail_mi():
    assert _nearest_rail_mi([], 41.9, -87.7) is None  # no stations -> NULL
    far = _nearest_rail_mi([(42.5, -88.5)], 41.9, -87.7)
    near = _nearest_rail_mi([(42.5, -88.5), (41.9, -87.701)], 41.9, -87.7)
    assert near < far  # picks the nearest of several


def test_assemble_teardown_candidate():
    lat, lon = 41.9, -87.7
    spine = {"pin": "p-teardown", "class": "311", "lat": lat, "lon": lon}
    chars = {"char_land_sf": "5000", "char_bldg_sf": "1200", "char_yrblt": "1910"}
    # building 20k, land 180k -> imp_share = 0.10 (<= 0.25) -> teardown
    assess = {"mailed_tot": "200000", "mailed_bldg": "20000", "mailed_land": "180000"}
    _, _, _, attrs, _ = _assemble(spine, chars, assess, None)
    assert attrs["is_teardown_candidate"] is True


def test_teardown_requires_a_structure_and_year():
    lat, lon = 41.9, -87.7
    spine = {"pin": "p-noyr", "class": "311", "lat": lat, "lon": lon}
    # land-dominant value but no year_built and no bldg_sqft -> not determinable -> NULL
    assess = {"mailed_tot": "200000", "mailed_bldg": "20000", "mailed_land": "180000"}
    _, _, _, attrs, _ = _assemble(spine, None, assess, None)
    assert "is_teardown_candidate" not in attrs


def test_upside_null_distinct_from_low_when_zoning_missing():
    lat, lon = 41.9, -87.7
    spine = {"pin": "p-nozone", "class": "311", "lat": lat, "lon": lon}
    chars = {"char_land_sf": "5000", "char_bldg_sf": "2000", "char_yrblt": "1995"}
    assess = {"mailed_tot": "250000", "mailed_bldg": "180000", "mailed_land": "70000"}
    # no zoning polygon -> no density_band -> upside_score must be NULL, never 0
    _, _, _, attrs, _ = _assemble(spine, chars, assess, None)
    assert "upside_score" not in attrs


# --- value_percentile (cross-parcel 2nd pass) -------------------------------


def _ppsf_row(pin: str, ppsf: float, *, ca: int = 24, lu: str = "multi_family", recency: int = 100):
    attrs = {"land_use_class": lu, "price_per_sf": ppsf, "sale_recency_days": recency}
    return (pin, 41.9, -87.7, attrs, [f"neighborhood:{ca}"])


def test_value_percentile_ranks_within_ca_use():
    # 40 multi_family parcels in CA 24 with ascending $/sqft (>= min_peers of 30).
    rows = [_ppsf_row(f"p{i}", ppsf=float(i + 1)) for i in range(40)]
    _compute_value_percentile(rows)
    pctiles = [a["value_percentile"] for (_p, _la, _lo, a, _r) in rows]
    assert pctiles[0] == 0                      # cheapest -> bottom of the distribution
    assert pctiles == sorted(pctiles)           # monotonic with $/sqft
    assert max(pctiles) < 100


def test_value_percentile_excludes_stale_and_priceless_sales():
    rows = [_ppsf_row(f"p{i}", ppsf=float(i + 1)) for i in range(35)]
    stale = ("p-stale", 41.9, -87.7,
             {"land_use_class": "multi_family", "price_per_sf": 1.0, "sale_recency_days": 4000}, ["neighborhood:24"])
    no_sale = ("p-nosale", 41.9, -87.7,
               {"land_use_class": "multi_family"}, ["neighborhood:24"])
    rows += [stale, no_sale]
    _compute_value_percentile(rows)
    assert "value_percentile" not in stale[3]    # sale older than 36mo -> not qualifying
    assert "value_percentile" not in no_sale[3]   # no sale at all -> never back-filled


def test_value_percentile_thin_ca_falls_back_to_citywide():
    # CA 24 has only 5 multi_family (thin), but citywide (CA 24 + CA 8) has 35 (>= 30).
    rows = [_ppsf_row(f"a{i}", ppsf=float(i + 1), ca=24) for i in range(5)]
    rows += [_ppsf_row(f"b{i}", ppsf=float(i + 1), ca=8) for i in range(30)]
    _compute_value_percentile(rows)
    # The thin-CA parcels still get a percentile (computed against the citywide pool).
    assert all("value_percentile" in a for (_p, _la, _lo, a, _r) in rows if a["land_use_class"] == "multi_family")


def test_value_percentile_all_thin_stays_null():
    rows = [_ppsf_row(f"p{i}", ppsf=float(i + 1)) for i in range(10)]  # 10 total < 30 anywhere
    _compute_value_percentile(rows)
    assert all("value_percentile" not in a for (_p, _la, _lo, a, _r) in rows)


# --- populated_fields manifest ----------------------------------------------


def test_populated_fields_lists_real_fields_and_omits_thin_ones():
    rows = [
        ("p1", 41.9, -87.7,
         {"land_use_class": "multi_family", "total_assessed_value": 250000.0, "upside_score": 60},
         ["neighborhood:24"]),
        ("p2", 41.8, -87.6,
         {"land_use_class": "commercial", "total_assessed_value": 100000.0},
         ["neighborhood:24"]),
    ]
    fields = _populated_fields(rows)
    assert "land_use" in fields            # land_use_class -> land_use filter
    assert "assessed_value" in fields      # total_assessed_value -> assessed_value filter
    assert "upside_score" in fields        # >=1 parcel has it
    assert "neighborhood" in fields        # region present
    assert "value_percentile" not in fields  # nobody got one -> recipe auto-downgrades
    assert "floodplain" not in fields        # deferred field, never populated


# --- recipe result counts (honest "Live · N" / "No matches yet") -------------


def test_recipe_counts_evaluates_recipes_against_the_snapshot():
    rows = [
        ("p1", 41.9, -87.7, {"land_use_class": "multi_family", "sale_recency_days": 30}, ["neighborhood:24"]),
        ("p2", 41.9, -87.7, {"land_use_class": "commercial", "sale_recency_days": 100}, ["neighborhood:24"]),
        ("p3", 41.9, -87.7, {"land_use_class": "multi_family", "sale_recency_days": 900}, ["neighborhood:24"]),
    ]
    counts = _recipe_counts(rows)
    # fresh_comps = (multi_family|commercial) AND sale within 180d -> p1 + p2 (p3 stale)
    assert counts["fresh_comps"] == 2
    # undervalued_mf = multi_family AND value_percentile <= 25; none have a percentile -> 0.
    # This is the LIVE-but-empty case: its FIELDS may be populated yet the recipe returns 0.
    assert counts["undervalued_mf"] == 0


def test_write_read_meta_roundtrips_recipe_counts(tmp_path):
    from backend.discovery.parcel_index import write_index
    p = tmp_path / "idx.db"
    write_index(
        p, data_version="v1", built_at=1, community_areas=[24],
        rows=[("p1", 41.9, -87.7, {"land_use_class": "multi_family"}, ["neighborhood:24"])],
        populated_fields=["land_use"], recipe_counts={"teardown": 5, "fresh_comps": 0},
    )
    meta = read_meta(p)
    assert meta is not None
    assert meta.recipe_counts == {"teardown": 5, "fresh_comps": 0}
    assert meta.populated_fields == ["land_use"]


# --- assessment join: skip the in-progress (valueless) year ------------------


async def test_batch_latest_passes_where_extra():
    """The assessment join ANDs a value-present predicate so it skips the null in-progress year."""
    seen_where: list[str] = []

    async def fake_socrata_get(dataset, params, **kw):
        seen_where.append(params["$where"])
        return [{"pin": "p1", "mailed_tot": "62000"}]

    import backend.discovery.index_build as mod

    orig = mod.socrata_get
    mod.socrata_get = fake_socrata_get
    try:
        out = await ib._batch_latest(
            "ds", ["p1"], "year", None, ib.get_settings(),
            where_extra="(mailed_tot IS NOT NULL OR certified_tot IS NOT NULL OR board_tot IS NOT NULL)",
        )
    finally:
        mod.socrata_get = orig
    assert out["p1"]["mailed_tot"] == "62000"
    assert "mailed_tot IS NOT NULL" in seen_where[0]
    assert "pin in (" in seen_where[0]


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

    async def fake_batch(dataset, pins, order_field, client, settings, *, where_extra=None):
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

    # The build writes a field-readiness manifest that de-dormants the page.
    meta = read_meta(tmp_path / "idx.db")
    assert meta is not None
    assert {"land_use", "tif", "neighborhood"} <= set(meta.populated_fields)
    assert "value_percentile" not in meta.populated_fields  # no qualifying sales in this build


async def test_build_index_degrades_when_a_layer_fails(tmp_path, monkeypatch):
    """A transient layer failure leaves its flag False instead of aborting the build."""
    async def boom(*a, **k):
        raise RuntimeError("503 Service Temporarily Unavailable")

    async def fake_ez(*a, **k):
        return []

    async def fake_spine(ca, *, client=None):
        return [{"pin": "p1", "pin_digits": "14311000010000", "class": "311",
                 "lat": 41.9, "lon": -87.7}]

    async def fake_batch(dataset, pins, order_field, client, settings, *, where_extra=None):
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
