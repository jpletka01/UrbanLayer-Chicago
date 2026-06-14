"""Step 7 tests — wire contracts for /api/discovery/registry and /api/discovery/search (07)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.discovery import parcel_source
from backend.discovery.parcel import DictParcel, default_source
from backend.main import app

VERSION = "api-test-v1"


def _pins(body: dict) -> list[str]:
    """Ordered pins from the hydrated rows (the wire returns rows, not bare pins)."""
    return [row["pin"] for row in body["result"]["rows"]]


@pytest.fixture
def client():
    parcel_source.set_snapshot(VERSION, [
        DictParcel("p1", {"land_use_class": "residential", "in_tif_district": True, "land_sqft": 5000}),
        DictParcel("p2", {"land_use_class": "commercial", "in_tif_district": True, "land_sqft": 8000}),
        DictParcel("p3", {"land_use_class": "residential", "in_tif_district": False, "land_sqft": 4000}),
    ])
    yield TestClient(app)
    parcel_source._current_version = None
    default_source.clear()


# --- GET /api/discovery/registry ------------------------------------------------


def test_registry_endpoint(client):
    r = client.get("/api/discovery/registry")
    assert r.status_code == 200
    body = r.json()
    assert body["version"]
    assert len(body["filters"]) == 32
    assert body["defaultSort"] == {"key": "assessed_value", "dir": "asc"}
    # PR4 critical default: the api fixture loads a snapshot with NO meta, so coverage is
    # "none" and populatedFields is empty — the page reads fully dormant, never "all".
    assert body["coverage"]["mode"] == "none"
    assert body["coverage"]["liveAreas"] == []
    assert body["populatedFields"] == []


# --- POST /api/discovery/search -------------------------------------------------


def test_search_ui_filter(client):
    r = client.post("/api/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["dataVersion"] == VERSION
    assert _pins(body) == ["p1", "p3"]
    assert body["result"]["total"] == 2
    # INV-4: canonical CQS echoed with source tagged user
    assert body["cqs"]["filters"]["land_use"]["source"] == "user"
    assert body["diagnostics"]["resultCount"] == 2


def test_search_text_is_compiled_server_side(client):
    r = client.post("/api/discovery/search", json={"text": "tif"})
    body = r.json()
    assert _pins(body) == ["p1", "p2"]
    assert body["cqs"]["filters"]["tif"]["source"] == "text"
    assert body["cqs"]["meta"]["rawText"] == "tif"


def test_search_user_and_text_merge(client):
    r = client.post("/api/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
        "text": "tif",
    })
    body = r.json()
    # residential AND tif → p1 only
    assert _pins(body) == ["p1"]


def test_search_empty_returns_all_and_broad(client):
    r = client.post("/api/discovery/search", json={})
    body = r.json()
    assert body["result"]["total"] == 3
    assert body["diagnostics"]["broad"] is True  # 0 filters < broadMinFilters
    assert body["diagnostics"]["appliedFilters"] == 0


def test_search_sort_override(client):
    r = client.post("/api/discovery/search", json={"sort": {"key": "lot_size", "dir": "desc"}})
    body = r.json()
    # 8000(p2), 5000(p1), 4000(p3)
    assert _pins(body) == ["p2", "p1", "p3"]
    assert body["cqs"]["sort"] == {"key": "lot_size", "dir": "desc"}


def test_search_drops_invalid_predicate_and_reports_it(client):
    r = client.post("/api/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": []}},  # empty enum → dropped
    })
    body = r.json()
    assert "land_use" not in body["cqs"]["filters"]
    assert body["diagnostics"]["droppedInvalid"] == [{"filterId": "land_use", "reason": "empty enum"}]
    assert body["result"]["total"] == 3  # no constraint applied


def test_search_zero_result_includes_most_restrictive(client):
    r = client.post("/api/discovery/search", json={
        "userFilters": {
            "land_use": {"kind": "enum", "values": ["industrial"]},  # none match
            "tif": {"kind": "flag", "value": True},
        },
    })
    body = r.json()
    assert body["result"]["total"] == 0
    mr = {row["filterId"]: row["countWithoutIt"] for row in body["diagnostics"]["mostRestrictive"]}
    assert mr == {"land_use": 2, "tif": 0}  # removing land_use surfaces the 2 tif parcels


def test_search_is_deterministic_across_the_wire(client):
    payload = {"userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}}}
    first = client.post("/api/discovery/search", json=payload).json()
    second = client.post("/api/discovery/search", json=payload).json()
    assert first["cqs"] == second["cqs"]
    assert _pins(first) == _pins(second)


# --- PR1: result.rows hydration + pagination + 0/exempt sort ---------------------


def test_search_hydrates_rows_from_snapshot(client):
    # Rows carry the hydrated display fields, in evaluated order, keyed off the snapshot.
    body = client.post("/api/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
        "sort": {"key": "lot_size", "dir": "desc"},
    }).json()
    rows = body["result"]["rows"]
    assert [r["pin"] for r in rows] == ["p1", "p3"]  # 5000 then 4000, desc
    assert rows[0]["land_use"] == "residential"
    assert rows[0]["lot_sqft"] == 5000
    # sortValue surfaces the active sort key's value (land_sqft here).
    assert rows[0]["sortValue"] == 5000
    # Derived fields (not yet computed by the index) hydrate as null.
    assert rows[0]["upside_score"] is None
    assert rows[0]["is_teardown_candidate"] is False
    assert body["result"]["nextOffset"] is None  # all rows fit one window


def test_search_paginates_with_limit_offset():
    parcel_source.set_snapshot("pg-v1", [
        DictParcel(f"x{i}", {"land_use_class": "residential", "land_sqft": i})
        for i in range(5)
    ])
    try:
        client = TestClient(app)
        first = client.post("/api/discovery/search", json={
            "sort": {"key": "lot_size", "dir": "asc"}, "limit": 2, "offset": 0,
        }).json()
        assert [r["pin"] for r in first["result"]["rows"]] == ["x0", "x1"]
        assert first["result"]["total"] == 5
        assert first["result"]["nextOffset"] == 2
        second = client.post("/api/discovery/search", json={
            "sort": {"key": "lot_size", "dir": "asc"}, "limit": 2, "offset": 2,
        }).json()
        assert [r["pin"] for r in second["result"]["rows"]] == ["x2", "x3"]
        assert second["result"]["nextOffset"] == 4
        last = client.post("/api/discovery/search", json={
            "sort": {"key": "lot_size", "dir": "asc"}, "limit": 2, "offset": 4,
        }).json()
        assert [r["pin"] for r in last["result"]["rows"]] == ["x4"]
        assert last["result"]["nextOffset"] is None  # window reaches the end
    finally:
        parcel_source._current_version = None
        default_source.clear()


def _exempt_snapshot(tmp_path):
    """West-Town-ish fixture with an exempt parcel and a $0 parcel, via the real
    write_index -> read_index path (so derive_sort_fields runs)."""
    from backend.discovery.parcel_index import read_index, write_index

    path = tmp_path / "discovery_index.db"
    write_index(
        path,
        data_version="exempt-v1",
        built_at=1,
        community_areas=[24],
        rows=[
            ("a", 41.9, -87.6, {"land_use_class": "residential", "total_assessed_value": 200000}, []),
            ("b", 41.9, -87.6, {"land_use_class": "residential", "total_assessed_value": 100000}, []),
            ("c", 41.9, -87.6, {"land_use_class": "exempt", "total_assessed_value": 9_000_000}, []),
            ("d", 41.9, -87.6, {"land_use_class": "residential", "total_assessed_value": 0}, []),
        ],
    )
    data_version, parcels = read_index(path)
    parcel_source.set_snapshot(data_version, parcels)


def test_exempt_and_zero_assessed_sort_last(tmp_path):
    # PR3 0/exempt rule (reconciled): a sort-only field (total_assessed_value_sortkey) is
    # null for exempt/$0, so the evaluator's existing missing-last ordering puts them last
    # under an ascending assessed_value sort — comparator untouched, real value preserved.
    _exempt_snapshot(tmp_path)
    try:
        client = TestClient(app)
        rows = client.post("/api/discovery/search", json={
            "sort": {"key": "assessed_value", "dir": "asc"},
        }).json()["result"]["rows"]
        # 100k, 200k, then exempt + $0 last (tie broken by PIN asc: c before d).
        assert [r["pin"] for r in rows] == ["b", "a", "c", "d"]
        # Display keeps the TRUE value — exempt shows its real 9M, $0 shows 0, and they
        # remain distinguishable from genuinely-missing data (which would be null).
        assert rows[0]["assessed_value"] == 100000  # b
        assert rows[2]["assessed_value"] == 9_000_000  # c (exempt, real value shown)
        assert rows[3]["assessed_value"] == 0  # d ($0, real value shown)
        # sortValue mirrors the sort key (null for the exempt/$0 rows that sort last).
        assert rows[2]["sortValue"] is None and rows[3]["sortValue"] is None
        assert rows[0]["sortValue"] == 100000
    finally:
        parcel_source._current_version = None
        default_source.clear()


def test_assessed_value_filter_matches_exempt_and_zero_by_true_value(tmp_path):
    # The assessed_value FILTER stays on the real value: exempt/$0 are NOT silently
    # excluded — they match by their true assessed value. (If we later decide the filter
    # SHOULD exclude them, that is a separate signed-off product change.)
    _exempt_snapshot(tmp_path)
    try:
        client = TestClient(app)
        # High floor → only the exempt parcel's true 9M qualifies.
        hi = client.post("/api/discovery/search", json={
            "userFilters": {"assessed_value": {"kind": "range", "min": 5_000_000}},
        }).json()
        assert [r["pin"] for r in hi["result"]["rows"]] == ["c"]
        # Exact-$0 band → the $0 parcel qualifies by its true value.
        zero = client.post("/api/discovery/search", json={
            "userFilters": {"assessed_value": {"kind": "range", "min": 0, "max": 0}},
        }).json()
        assert [r["pin"] for r in zero["result"]["rows"]] == ["d"]
    finally:
        parcel_source._current_version = None
        default_source.clear()


def test_search_returns_json_not_spa_fallback(client):
    # Guards the /api-prefix lesson: a 200 can be the SPA index.html fallback. Assert the
    # response is real JSON from FastAPI, not HTML.
    r = client.post("/api/discovery/search", json={})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "<!doctype html" not in r.text.lower()
    assert "rows" in r.json()["result"]


# --- PR4: coverage + populatedFields (registry response, sourced from index meta) ------


def _registry_with_meta(community_areas, populated_fields, recipe_counts=None):
    from backend.discovery.parcel_index import IndexMeta

    parcel_source.set_snapshot(
        "cov-v1",
        [DictParcel("p1", {"land_use_class": "residential"})],
        meta=IndexMeta(
            data_version="cov-v1",
            community_areas=community_areas,
            populated_fields=populated_fields,
            built_at=1_700_000_000,
            recipe_counts=recipe_counts or {},
        ),
    )
    try:
        return TestClient(app).get("/api/discovery/registry").json()
    finally:
        parcel_source._current_version = None
        parcel_source._current_meta = None
        default_source.clear()


def test_registry_partial_coverage_echoes_meta():
    body = _registry_with_meta([24], ["land_use", "lot_size", "assessed_value"])
    assert body["coverage"]["mode"] == "partial"
    assert body["coverage"]["liveAreas"] == [24]
    assert body["coverage"]["asOf"]  # ISO date present
    # populatedFields drives BOTH consumers (panel disable + recipe badges) from one source.
    assert body["populatedFields"] == ["assessed_value", "land_use", "lot_size"]


def test_registry_echoes_recipe_counts():
    # Recipe result counts ride the registry response so the shelf shows "Live · N" /
    # "No matches yet" instead of inferring LIVE from field-presence (which mislabels a
    # recipe whose fields are populated but whose subset is empty).
    body = _registry_with_meta([24], ["land_use"], recipe_counts={"teardown": 12, "undervalued_mf": 0})
    assert body["recipeCounts"] == {"teardown": 12, "undervalued_mf": 0}


def test_registry_recipe_counts_default_empty_when_dormant():
    parcel_source._current_version = None  # no index -> dormant
    parcel_source._current_meta = None
    body = TestClient(app).get("/api/discovery/registry").json()
    assert body["recipeCounts"] == {}


def test_registry_full_coverage_is_mode_all():
    body = _registry_with_meta(list(range(1, 78)), ["land_use"])  # all 77 CAs
    assert body["coverage"]["mode"] == "all"
    assert len(body["coverage"]["liveAreas"]) == 77


def test_registry_empty_populated_fields_when_meta_absent():
    # Guardrail: a built index whose meta carries NO populated fields → everything reads
    # "coming". Never defaults to all-available.
    body = _registry_with_meta([24], [])
    assert body["populatedFields"] == []
    assert body["coverage"]["mode"] == "partial"  # geography known, but no fields populated


def test_pin_lookup_is_memoized_and_invalidates_on_snapshot_change():
    # Same dataVersion -> same cached dict object (not rebuilt O(N) per request).
    parcel_source.set_snapshot("mz-v1", [DictParcel("p1", {"land_use_class": "residential"})])
    try:
        first = parcel_source.pin_lookup("mz-v1")
        assert parcel_source.pin_lookup("mz-v1") is first  # cached, identical object
        assert set(first) == {"p1"}
        # A new snapshot invalidates the cache -> rebuilt with the new parcels.
        parcel_source.set_snapshot("mz-v2", [DictParcel("p2"), DictParcel("p3")])
        rebuilt = parcel_source.pin_lookup("mz-v2")
        assert rebuilt is not first
        assert set(rebuilt) == {"p2", "p3"}
    finally:
        parcel_source._current_version = None
        parcel_source._current_meta = None
        parcel_source._pin_index = None
        parcel_source._pin_index_version = None
        default_source.clear()


def test_coverage_never_enters_the_cqs_path(client):
    # Guardrail #1: coverage is a registry-only presentational concern. It must never
    # appear in the search response's CQS (chips) nor as a top-level result field.
    body = client.post("/api/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
    }).json()
    assert "coverage" not in body  # not on the SearchResponse
    assert "coverage" not in body["cqs"]  # not in the canonical CQS
    assert "coverage" not in body["cqs"]["filters"]  # not a filter/chip


# --- PR6: /search/pins (full ordered coord set, single-resolver sequence parity) --------


def test_search_pins_sequence_matches_search(client):
    # Guardrail #1: /search/pins goes through the same _resolve path, so its ordered PIN
    # sequence is identical to /search's — under a NON-default sort, so a dropped-sort bug
    # (which total-parity would miss) would desync the order and fail here.
    payload = {"sort": {"key": "lot_size", "dir": "desc"}}
    search = client.post("/api/discovery/search", json=payload).json()
    pins = client.post("/api/discovery/search/pins", json=payload).json()
    search_seq = [r["pin"] for r in search["result"]["rows"]]
    pins_seq = [p["pin"] for p in pins["points"]]
    assert search_seq == ["p2", "p1", "p3"]  # lot_size desc
    # The /search window is a prefix of the full /search/pins sequence — exact, not just total.
    assert pins_seq[: len(search_seq)] == search_seq
    assert pins["total"] == search["result"]["total"] == 3
    assert pins["truncated"] is False


def test_search_pins_carries_coords_and_upside(client):
    pins = client.post("/api/discovery/search/pins", json={}).json()
    p = pins["points"][0]
    assert set(p.keys()) == {"pin", "lat", "lon", "upside", "landUse"}
    assert p["upside"] is None  # not computed until PR-INDEX → FE renders a "no data" swatch


def test_search_pins_caps_and_flags_truncation(monkeypatch):
    import backend.discovery.api as api

    monkeypatch.setattr(api, "MAX_MAP_POINTS", 2)
    parcel_source.set_snapshot("cap-v1", [
        DictParcel(f"c{i}", {"land_use_class": "residential", "land_sqft": i}) for i in range(5)
    ])
    try:
        pins = TestClient(app).post(
            "/api/discovery/search/pins", json={"sort": {"key": "lot_size", "dir": "asc"}}
        ).json()
        assert pins["total"] == 5
        assert len(pins["points"]) == 2  # capped
        assert [p["pin"] for p in pins["points"]] == ["c0", "c1"]  # the ordered prefix
        assert pins["truncated"] is True  # "refine to map the rest"
    finally:
        parcel_source._current_version = None
        default_source.clear()


def test_search_pins_returns_json_not_spa_fallback(client):
    r = client.post("/api/discovery/search/pins", json={})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "points" in r.json()


# --- PR7: /search/export (full match set, server-side, premium-gated CSV) ----------------


def _csv_rows(text: str) -> list[list[str]]:
    import csv as _csv
    import io as _io

    return list(_csv.reader(_io.StringIO(text)))


def test_export_streams_full_match_set_with_human_headers(client):
    # Premium gate passes in dev mode (admin). Exports ALL matches, not a window.
    r = client.post("/api/discovery/search/export", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
        "limit": 1,  # a tiny list window must NOT shrink the export
    })
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in r.headers["content-disposition"]
    rows = _csv_rows(r.text)
    header, *data = rows
    # Hand-authored labels, not snake_case field ids.
    assert "PIN" in header and "Property use" in header and "Assessed value" in header
    assert "land_use" not in header and "land_use_class" not in header
    # Full set: both residential parcels (p1, p3), regardless of the limit:1 window.
    assert {row[0] for row in data} == {"p1", "p3"}


def test_export_order_matches_search(client):
    payload = {"sort": {"key": "lot_size", "dir": "desc"}}
    search = client.post("/api/discovery/search", json=payload).json()
    exported = _csv_rows(client.post("/api/discovery/search/export", json=payload).text)
    pins_in_csv = [row[0] for row in exported[1:]]
    assert pins_in_csv == [r["pin"] for r in search["result"]["rows"]] == ["p2", "p1", "p3"]


def test_export_keeps_real_assessed_value_for_exempt(tmp_path):
    _exempt_snapshot(tmp_path)  # c = exempt w/ real 9M, d = $0
    try:
        rows = _csv_rows(TestClient(app).post("/api/discovery/search/export", json={}).text)
        header = rows[0]
        av_col = header.index("Assessed value")
        by_pin = {row[0]: row for row in rows[1:]}
        assert by_pin["c"][av_col] == "9000000"  # exempt → true value, honest
        assert by_pin["d"][av_col] == "0"  # $0 → true value
    finally:
        parcel_source._current_version = None
        parcel_source._current_meta = None
        default_source.clear()


def test_export_filename_reflects_filters_and_version(client):
    r = client.post("/api/discovery/search/export", json={
        "userFilters": {"tif": {"kind": "flag", "value": True}},
    })
    cd = r.headers["content-disposition"]
    assert "discovery_tif_" in cd
    assert "api-test-v1" in cd and cd.endswith('.csv"')


def test_export_is_premium_gated(client, monkeypatch):
    import backend.auth as auth

    async def _free(_request):
        return {"id": "u", "email": "e", "tier": "free"}

    monkeypatch.setattr(auth, "get_current_user", _free)
    r = client.post("/api/discovery/search/export", json={})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "upgrade_required"


def test_export_requires_auth(client, monkeypatch):
    import backend.auth as auth

    async def _anon(_request):
        return None

    monkeypatch.setattr(auth, "get_current_user", _anon)
    r = client.post("/api/discovery/search/export", json={})
    assert r.status_code == 401


# --- PR9: free-tier teaser cap (server-enforced) + gated flag ---------------------------


# /search uses Depends(get_current_user) (captured at decoration) → override the
# dependency rather than monkeypatching the module attr (which wouldn't take effect).
def _as_free():
    import backend.discovery.api as api

    app.dependency_overrides[api.get_current_user] = lambda: {"id": "u", "email": "e", "tier": "free"}


def _restore_tier():
    app.dependency_overrides.clear()


def test_search_free_tier_is_capped_and_gated():
    parcel_source.set_snapshot("free-v1", [
        DictParcel(f"f{i:02d}", {"land_use_class": "residential", "land_sqft": i}) for i in range(25)
    ])
    _as_free()
    try:
        body = TestClient(app).post("/api/discovery/search", json={
            "sort": {"key": "lot_size", "dir": "asc"}, "limit": 50,  # request 50 — must be ignored
        }).json()
        rows = body["result"]["rows"]
        assert len(rows) == 10  # FREE_ROW_CAP, regardless of requested limit
        assert body["result"]["total"] == 25  # TRUE total, not the capped count
        assert body["result"]["gated"] is True
        assert body["result"]["nextOffset"] is None  # no paging past the wall
        # The 10 shown are the TOP ranked (the teaser is "your 10 best leads").
        assert [r["pin"] for r in rows] == [f"f{i:02d}" for i in range(10)]
    finally:
        _restore_tier()
        parcel_source._current_version = None
        default_source.clear()


def test_search_free_tier_cannot_page_past_the_cap():
    parcel_source.set_snapshot("free-v2", [
        DictParcel(f"f{i:02d}", {"land_use_class": "residential", "land_sqft": i}) for i in range(25)
    ])
    _as_free()
    try:
        # Even with an explicit offset, the server refuses to serve rows 11+.
        body = TestClient(app).post("/api/discovery/search", json={
            "sort": {"key": "lot_size", "dir": "asc"}, "offset": 10, "limit": 10,
        }).json()
        assert [r["pin"] for r in body["result"]["rows"]] == [f"f{i:02d}" for i in range(10)]
        assert body["result"]["gated"] is True
    finally:
        _restore_tier()
        parcel_source._current_version = None
        default_source.clear()


def test_search_premium_is_not_gated(client):
    # Dev mode → admin (pro). Full window, not gated.
    body = client.post("/api/discovery/search", json={}).json()
    assert body["result"]["gated"] is False


def test_free_tier_top_rows_keep_upside_and_full_fields():
    parcel_source.set_snapshot("free-v3", [
        DictParcel("f0", {"land_use_class": "multi_family", "upside_score": 86, "total_assessed_value": 118400}),
    ])
    _as_free()
    try:
        body = TestClient(app).post("/api/discovery/search", json={}).json()
        assert body["result"]["gated"] is True
        row = body["result"]["rows"][0]
        assert row["upside_score"] == 86  # NOT stripped on free rows (Jack's call)
        assert row["assessed_value"] == 118400
    finally:
        _restore_tier()
        parcel_source._current_version = None
        default_source.clear()


def test_search_pins_carries_landuse_for_free_map_coloring(client):
    parcel_source.set_snapshot("lu-v1", [DictParcel("p9", {"land_use_class": "commercial"})])
    try:
        pts = TestClient(app).post("/api/discovery/search/pins", json={}).json()["points"]
        assert pts[0]["landUse"] == "commercial"
    finally:
        parcel_source._current_version = None
        default_source.clear()
