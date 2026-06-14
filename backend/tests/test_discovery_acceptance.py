"""Step 10 (backend) — the headline acceptance test (08 definition of done).

Mode equivalence: topic, text, and UI inputs that compile to *equal* canonical CQS
return *identical* pins — the single-evaluator/determinism invariants (INV-1/INV-2/INV-3)
observed end-to-end through the wire. The frontend's own compiler purity tests ship with
steps 8–9; this proves the property the whole architecture exists to guarantee.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.discovery import parcel_source
from backend.discovery.cqs import CQS, cqs_equal
from backend.discovery.parcel import DictParcel, default_source
from backend.main import app

VERSION = "accept-v1"


@pytest.fixture
def client():
    parcel_source.set_snapshot(VERSION, [
        DictParcel("m1", {"land_use_class": "multi_family", "in_tif_district": True}),
        DictParcel("m2", {"land_use_class": "multi_family", "in_tif_district": False}),
        DictParcel("m3", {"land_use_class": "commercial", "in_tif_district": True}),
    ])
    yield TestClient(app)
    parcel_source._current_version = None
    default_source.clear()


def _search(client, **payload) -> dict:
    r = client.post("/api/discovery/search", json=payload)
    assert r.status_code == 200
    return r.json()


def test_topic_text_and_ui_equal_cqs_return_identical_pins(client):
    # UI mode: panel selections → userFilters.
    ui = _search(client, userFilters={
        "land_use": {"kind": "enum", "values": ["multi_family"]},
        "tif": {"kind": "flag", "value": True},
    })
    # Text mode: a free-text phrase parsed server-side to the same constraints.
    text = _search(client, text="multifamily tif")
    # Topic mode: a preset, FE-expanded into userFilters (topicId is inert telemetry).
    topic = _search(client, userFilters={
        "land_use": {"kind": "enum", "values": ["multi_family"]},
        "tif": {"kind": "flag", "value": True},
    }, topicId="vacant_multifamily")

    # Identical results across all three modes.
    assert ui["result"]["pins"] == text["result"]["pins"] == topic["result"]["pins"] == ["m1"]

    # And their canonical CQS are equal (source/meta excluded by canonical form).
    ui_cqs = CQS.model_validate(ui["cqs"])
    text_cqs = CQS.model_validate(text["cqs"])
    topic_cqs = CQS.model_validate(topic["cqs"])
    assert cqs_equal(ui_cqs, text_cqs)
    assert cqs_equal(ui_cqs, topic_cqs)


def test_equal_cqs_implies_equal_pins_is_the_only_difference_source(client):
    # Two envelopes that differ ONLY in provenance/meta must yield identical pins.
    a = _search(client, userFilters={"tif": {"kind": "flag", "value": True}})
    b = _search(client, text="tif")  # same constraint, different source
    assert cqs_equal(CQS.model_validate(a["cqs"]), CQS.model_validate(b["cqs"]))
    assert a["result"]["pins"] == b["result"]["pins"] == ["m1", "m3"]


def test_repeated_envelope_is_byte_identical_across_the_wire(client):
    payload = {
        "userFilters": {"land_use": {"kind": "enum", "values": ["multi_family"]}},
        "text": "tif",
        "sort": {"key": "pin", "dir": "desc"},
    }
    first = _search(client, **payload)
    second = _search(client, **payload)
    assert first == second  # full SearchResponse byte-identical (per dataVersion)
