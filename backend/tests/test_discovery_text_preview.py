"""POST /api/discovery/text-preview: the compile half of a search, with no evaluation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.discovery import parcel_source
from backend.discovery.api import SearchRequest, _resolve
from backend.discovery.parcel import DictParcel, default_source
from backend.discovery.text_preview import MAX_TEXT_CHARS
from backend.main import app

VERSION = "preview-v1"


@pytest.fixture
def client():
    parcel_source.set_snapshot(VERSION, [DictParcel("p1", {"land_use_class": "multi_family", "in_tif_district": True})])
    yield TestClient(app)
    parcel_source._current_version = None
    default_source.clear()


def _preview(client, text):
    r = client.post("/api/discovery/text-preview", json={"text": text})
    assert r.status_code == 200
    return r.json()


def test_a_phrase_the_compiler_understands_returns_its_filters_and_no_residual(client):
    body = _preview(client, "multifamily built before 1950 with a TIF")
    understood = {u["filterId"]: u["predicate"] for u in body["understood"]}
    assert understood == {
        "year_built": {"kind": "range", "min": None, "max": 1950.0},
        "land_use": {"kind": "enum", "values": ["multi_family"]},
        "tif": {"kind": "flag", "value": True},
    }
    assert body["residual"] == [] and body["droppedInvalid"] == []


def test_a_phrase_it_does_not_understand_returns_no_filters_and_the_words(client):
    # The case that, sent as a search, used to return every parcel.
    body = _preview(client, "teardown in logan square")
    assert body["understood"] == []
    assert body["residual"] == ["teardown", "logan", "square"]


def test_partly_understood_names_both_halves(client):
    body = _preview(client, "vacant multifamily near the L, built after 1990")
    assert {u["filterId"] for u in body["understood"]} == {"vacancy", "land_use", "year_built"}
    assert body["residual"] == ["l"]


def test_empty_text_is_understood_as_nothing(client):
    body = _preview(client, "")
    assert body == {"understood": [], "residual": [], "droppedInvalid": []}


def test_the_preview_equals_what_a_search_derives_from_the_same_text(client):
    """Same parse -> merge path as /search: the preview cannot promise filters a search would not use."""
    for text in ("multifamily built before 1950 with a TIF", "vacant land in a TIF", "teardown in logan square", ""):
        cqs, _result, dropped, _v = _resolve(SearchRequest(text=text))
        body = _preview(client, text)
        assert {u["filterId"]: u["predicate"] for u in body["understood"]} == {
            fid: a.predicate.model_dump() for fid, a in cqs.filters.items()
        }
        assert body["residual"] == cqs.meta.textResidual
        assert [d["filterId"] for d in body["droppedInvalid"]] == [d.filterId for d in dropped]


def test_compile_time_drops_are_reported_not_hidden(client, monkeypatch):
    """A compiled predicate the merge refuses is named, exactly as /search would drop it."""
    from backend.discovery import text_preview as tp
    from backend.discovery.cqs import CqsFragment, FilterAssignment, FlagPredicate, QueryMeta

    monkeypatch.setattr(
        tp, "parse",
        lambda text: CqsFragment(
            filters={"no_such_filter": FilterAssignment(predicate=FlagPredicate(value=True), source="text")},
            meta=QueryMeta(rawText=text, textResidual=["x"]),
        ),
    )
    body = _preview(client, "anything")
    assert body["understood"] == []
    assert body["droppedInvalid"] == [{"filterId": "no_such_filter", "reason": "unknown filter"}]


def test_it_never_evaluates(client, monkeypatch):
    """Every module under backend.discovery that holds an `evaluate` is made to fail if called."""
    import sys

    def boom(*a, **k):
        raise AssertionError("text-preview must not evaluate")

    for name, module in list(sys.modules.items()):
        if name.startswith("backend.discovery") and hasattr(module, "evaluate"):
            monkeypatch.setattr(module, "evaluate", boom)
    assert _preview(client, "vacant multifamily")["understood"]


def test_the_text_is_bounded(client):
    r = client.post("/api/discovery/text-preview", json={"text": "x" * (MAX_TEXT_CHARS + 1)})
    assert r.status_code == 422
    assert client.post("/api/discovery/text-preview", json={"text": "x" * MAX_TEXT_CHARS}).status_code == 200


def test_it_returns_json_not_the_spa_fallback(client):
    r = client.post("/api/discovery/text-preview", json={"text": "tif"})
    assert r.headers["content-type"].startswith("application/json")
