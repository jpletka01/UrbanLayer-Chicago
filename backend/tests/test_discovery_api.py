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
    assert len(body["filters"]) == 29
    assert body["defaultSort"] == {"key": "pin", "dir": "asc"}


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
