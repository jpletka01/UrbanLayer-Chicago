"""Step 7 tests — wire contracts for /discovery/registry and /discovery/search (07)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.discovery import parcel_source
from backend.discovery.parcel import DictParcel, default_source
from backend.main import app

VERSION = "api-test-v1"


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


# --- GET /discovery/registry ------------------------------------------------


def test_registry_endpoint(client):
    r = client.get("/discovery/registry")
    assert r.status_code == 200
    body = r.json()
    assert body["version"]
    assert len(body["filters"]) == 29
    assert body["defaultSort"] == {"key": "pin", "dir": "asc"}


# --- POST /discovery/search -------------------------------------------------


def test_search_ui_filter(client):
    r = client.post("/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["dataVersion"] == VERSION
    assert body["result"]["pins"] == ["p1", "p3"]
    assert body["result"]["total"] == 2
    # INV-4: canonical CQS echoed with source tagged user
    assert body["cqs"]["filters"]["land_use"]["source"] == "user"
    assert body["diagnostics"]["resultCount"] == 2


def test_search_text_is_compiled_server_side(client):
    r = client.post("/discovery/search", json={"text": "tif"})
    body = r.json()
    assert body["result"]["pins"] == ["p1", "p2"]
    assert body["cqs"]["filters"]["tif"]["source"] == "text"
    assert body["cqs"]["meta"]["rawText"] == "tif"


def test_search_user_and_text_merge(client):
    r = client.post("/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}},
        "text": "tif",
    })
    body = r.json()
    # residential AND tif → p1 only
    assert body["result"]["pins"] == ["p1"]


def test_search_empty_returns_all_and_broad(client):
    r = client.post("/discovery/search", json={})
    body = r.json()
    assert body["result"]["total"] == 3
    assert body["diagnostics"]["broad"] is True  # 0 filters < broadMinFilters
    assert body["diagnostics"]["appliedFilters"] == 0


def test_search_sort_override(client):
    r = client.post("/discovery/search", json={"sort": {"key": "lot_size", "dir": "desc"}})
    body = r.json()
    # 8000(p2), 5000(p1), 4000(p3)
    assert body["result"]["pins"] == ["p2", "p1", "p3"]
    assert body["cqs"]["sort"] == {"key": "lot_size", "dir": "desc"}


def test_search_drops_invalid_predicate_and_reports_it(client):
    r = client.post("/discovery/search", json={
        "userFilters": {"land_use": {"kind": "enum", "values": []}},  # empty enum → dropped
    })
    body = r.json()
    assert "land_use" not in body["cqs"]["filters"]
    assert body["diagnostics"]["droppedInvalid"] == [{"filterId": "land_use", "reason": "empty enum"}]
    assert body["result"]["total"] == 3  # no constraint applied


def test_search_zero_result_includes_most_restrictive(client):
    r = client.post("/discovery/search", json={
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
    first = client.post("/discovery/search", json=payload).json()
    second = client.post("/discovery/search", json=payload).json()
    assert first["cqs"] == second["cqs"]
    assert first["result"]["pins"] == second["result"]["pins"]
