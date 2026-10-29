"""Result cache in front of the single evaluator (INV-1, INV-2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.discovery import parcel as parcel_mod
from backend.discovery import parcel_source, result_cache
from backend.discovery.cqs import (
    CQS,
    EnumPredicate,
    FilterAssignment,
    QueryMeta,
    RangePredicate,
    SortSpec,
    SpatialScope,
)
from backend.discovery.evaluator import evaluate
from backend.discovery.parcel import DictParcel
from backend.discovery.result_cache import cached_evaluate
from backend.main import app

V1, V2 = "cache-v1", "cache-v2"


@pytest.fixture(autouse=True)
def _isolate_snapshot():
    parcel_mod.default_source.clear()
    yield
    parcel_mod.default_source.clear()


def _parcels(n=12, offset=0):
    return [
        DictParcel(f"p{i:03d}", {"land_use_class": "residential" if i % 2 else "commercial", "land_sqft": 1000 + 100 * ((i + offset) % 5)})
        for i in range(n)
    ]


def _cqs(filters=None, sort=None, scope=None, meta=None) -> CQS:
    return CQS(
        filters=filters or {},
        sort=sort or SortSpec(key="lot_size", dir="desc"),
        scope=scope or SpatialScope(),
        meta=meta or QueryMeta(),
    )


def _res_filter():
    return {"land_use": FilterAssignment(predicate=EnumPredicate(values=["residential"]))}


# --- correctness: a hit is exactly what a fresh evaluation returns ----------


def test_hit_equals_fresh_evaluation_and_is_immutable():
    parcel_mod.default_source.register(V1, _parcels())
    cqs = _cqs(_res_filter())
    first = cached_evaluate(cqs, V1)
    second = cached_evaluate(cqs, V1)
    fresh = evaluate(cqs, V1)
    assert second is first  # served from the cache
    assert list(first.pins) == fresh.pins and first.total == fresh.total
    assert first.excludedUnknown == fresh.excludedUnknown and first.dataVersion == V1
    assert isinstance(first.pins, tuple)
    assert result_cache.stats()["hits"] == 1 and result_cache.stats()["misses"] == 1


def test_key_ignores_meta_and_source_but_not_filters_sort_or_scope():
    parcel_mod.default_source.register(V1, _parcels())
    base = cached_evaluate(_cqs(_res_filter()), V1)

    # meta and every `source` tag are outside the canonical form (INV-2)
    tagged = {"land_use": FilterAssignment(predicate=EnumPredicate(values=["residential"]), source="text")}
    again = cached_evaluate(_cqs(tagged, meta=QueryMeta(topicId="t", rawText="residential", textResidual=["x"])), V1)
    assert again is base
    assert result_cache.stats()["entries"] == 1

    # ...but anything the evaluator reads splits the key
    cached_evaluate(_cqs(_res_filter(), sort=SortSpec(key="lot_size", dir="asc")), V1)
    cached_evaluate(_cqs({"lot_size": FilterAssignment(predicate=RangePredicate(min=1200))}), V1)
    cached_evaluate(_cqs(_res_filter(), scope=SpatialScope(mode="viewport", bbox=(0, 0, 1, 1))), V1)
    assert result_cache.stats()["entries"] == 4


def test_enum_value_order_does_not_split_the_key():
    parcel_mod.default_source.register(V1, _parcels())
    a = {"land_use": FilterAssignment(predicate=EnumPredicate(values=["residential", "commercial"]))}
    b = {"land_use": FilterAssignment(predicate=EnumPredicate(values=["commercial", "residential"]))}
    assert cached_evaluate(_cqs(a), V1) is cached_evaluate(_cqs(b), V1)


# --- invalidation: never serve an older snapshot -----------------------------


def test_new_data_version_drops_old_entries_and_serves_new_rows():
    parcel_mod.default_source.register(V1, _parcels(12))
    parcel_mod.default_source.register(V2, _parcels(6))
    cqs = _cqs(_res_filter())
    old = cached_evaluate(cqs, V1)
    new = cached_evaluate(cqs, V2)
    assert old.dataVersion == V1 and new.dataVersion == V2
    assert new.total == evaluate(cqs, V2).total != old.total
    assert result_cache.stats()["entries"] == 1  # V1's entry was dropped when V2's was stored


def test_replaced_snapshot_under_the_same_version_is_not_served_stale():
    cqs = _cqs(_res_filter())
    parcel_mod.default_source.register(V1, _parcels(12))
    before = cached_evaluate(cqs, V1)
    parcel_mod.default_source.register(V1, _parcels(6, offset=2))
    after = cached_evaluate(cqs, V1)
    assert after is not before
    assert list(after.pins) == evaluate(cqs, V1).pins and after.total != before.total


def test_set_snapshot_through_parcel_source_invalidates():
    cqs = _cqs()
    parcel_source.set_snapshot(V1, _parcels(5))
    assert cached_evaluate(cqs, V1).total == 5
    parcel_source.set_snapshot(V1, _parcels(9))
    assert cached_evaluate(cqs, V1).total == 9
    parcel_source._current_version = None


# --- failures raise and are never cached -------------------------------------


def test_failed_evaluation_raises_and_stores_nothing(monkeypatch):
    parcel_mod.default_source.register(V1, _parcels())
    calls = {"n": 0}
    real = result_cache.evaluate

    def flaky(cqs, version):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(cqs, version)

    monkeypatch.setattr(result_cache, "evaluate", flaky)
    with pytest.raises(RuntimeError):
        cached_evaluate(_cqs(), V1)
    assert result_cache.stats()["entries"] == 0
    assert cached_evaluate(_cqs(), V1).total == 12  # recomputed, not a cached failure


def test_unknown_version_raises_and_stores_nothing():
    with pytest.raises(KeyError):
        cached_evaluate(_cqs(), "no-such-version")
    assert result_cache.stats()["entries"] == 0


# --- memory bound -------------------------------------------------------------


def test_entry_count_is_bounded_and_lru_order_holds(monkeypatch):
    monkeypatch.setattr(result_cache, "MAX_ENTRIES", 3)
    parcel_mod.default_source.register(V1, _parcels())
    q = [_cqs({"lot_size": FilterAssignment(predicate=RangePredicate(min=1000 + i))}) for i in range(5)]
    for c in q[:3]:
        cached_evaluate(c, V1)
    cached_evaluate(q[0], V1)  # refresh q0 -> q1 is now least recently used
    cached_evaluate(q[3], V1)  # evicts q1
    assert result_cache.stats()["entries"] == 3
    hits = result_cache.stats()["hits"]
    cached_evaluate(q[0], V1)
    assert result_cache.stats()["hits"] == hits + 1  # q0 survived
    cached_evaluate(q[1], V1)
    assert result_cache.stats()["hits"] == hits + 1  # q1 was evicted (a miss)


def test_total_pin_budget_is_enforced_and_oversize_results_are_not_stored(monkeypatch):
    monkeypatch.setattr(result_cache, "MAX_TOTAL_PINS", 20)
    parcel_mod.default_source.register(V1, _parcels(12))
    for i in range(6):  # each result holds 12 - i pins
        cached_evaluate(_cqs({"lot_size": FilterAssignment(predicate=RangePredicate(min=1000))}, sort=SortSpec(key="pin", dir="asc" if i % 2 else "desc")), V1)
    assert result_cache.stats()["pins"] <= 20

    result_cache.clear()
    monkeypatch.setattr(result_cache, "MAX_TOTAL_PINS", 5)
    big = cached_evaluate(_cqs(), V1)  # 12 pins > budget: correct result, not stored
    assert big.total == 12 and list(big.pins) == evaluate(_cqs(), V1).pins
    assert result_cache.stats()["entries"] == 0


# --- through the API ----------------------------------------------------------


def test_repeated_api_search_is_a_cache_hit_with_identical_body():
    parcel_source.set_snapshot(V1, _parcels())
    client = TestClient(app)
    body = {"userFilters": {"land_use": {"kind": "enum", "values": ["residential"]}}}
    first = client.post("/api/discovery/search", json=body).json()
    misses = result_cache.stats()["misses"]
    second = client.post("/api/discovery/search", json=body).json()
    assert second == first
    assert result_cache.stats()["misses"] == misses  # no re-evaluation
    parcel_source._current_version = None


# --- coalescing + concurrency cap ----------------------------------------------


def _run_threads(targets):
    import threading

    out = [None] * len(targets)

    def wrap(i, fn):
        try:
            out[i] = fn()
        except BaseException as exc:  # noqa: BLE001 - collected for assertions
            out[i] = exc

    threads = [threading.Thread(target=wrap, args=(i, fn)) for i, fn in enumerate(targets)]
    for t in threads:
        t.start()
    return threads, out


def test_identical_concurrent_queries_evaluate_once(monkeypatch):
    import threading

    parcel_mod.default_source.register(V1, _parcels())
    release, calls = threading.Event(), {"n": 0}
    real = result_cache.evaluate

    def slow(cqs, version):
        calls["n"] += 1
        release.wait(5)
        return real(cqs, version)

    monkeypatch.setattr(result_cache, "evaluate", slow)
    threads, out = _run_threads([lambda: cached_evaluate(_cqs(_res_filter()), V1) for _ in range(6)])
    release.set()
    for t in threads:
        t.join(10)
    assert calls["n"] == 1  # whether a caller coalesced or hit the stored entry, no re-evaluation
    assert all(r is out[0] for r in out) and list(out[0].pins) == real(_cqs(_res_filter()), V1).pins


def test_a_shared_failure_reaches_every_waiter_and_is_not_cached(monkeypatch):
    import threading

    parcel_mod.default_source.register(V1, _parcels())
    release, calls = threading.Event(), {"n": 0}

    def failing(cqs, version):
        calls["n"] += 1
        release.wait(5)
        raise RuntimeError("source down")

    monkeypatch.setattr(result_cache, "evaluate", failing)
    threads, out = _run_threads([lambda: cached_evaluate(_cqs(), V1) for _ in range(4)])
    # let every thread register as leader or waiter before the leader fails
    deadline = 0
    while result_cache.stats()["coalesced"] < 3 and deadline < 500:
        threading.Event().wait(0.01)
        deadline += 1
    release.set()
    for t in threads:
        t.join(10)
    assert all(isinstance(r, RuntimeError) for r in out)
    assert calls["n"] == 1 and result_cache.stats()["entries"] == 0
    monkeypatch.undo()
    assert cached_evaluate(_cqs(), V1).total == 12  # the next request recomputes


def test_concurrent_distinct_evaluations_are_capped(monkeypatch):
    import threading
    import time

    parcel_mod.default_source.register(V1, _parcels())
    monkeypatch.setattr(result_cache, "_eval_slots", threading.BoundedSemaphore(2))
    state = {"now": 0, "max": 0, "calls": 0}
    gate = threading.Lock()
    real = result_cache.evaluate

    def tracked(cqs, version):
        with gate:
            state["now"] += 1
            state["calls"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.03)
        try:
            return real(cqs, version)
        finally:
            with gate:
                state["now"] -= 1

    monkeypatch.setattr(result_cache, "evaluate", tracked)
    queries = [_cqs({"lot_size": FilterAssignment(predicate=RangePredicate(min=900 + i))}) for i in range(8)]
    threads, out = _run_threads([(lambda c=c: cached_evaluate(c, V1)) for c in queries])
    for t in threads:
        t.join(15)
    assert state["calls"] == 8 and state["max"] <= 2
    assert [r.total for r in out] == [evaluate(c, V1).total for c in queries]
