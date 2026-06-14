"""Step 2 tests — CQS models, predicate validity, canonical form + equality (02)."""

from __future__ import annotations

from backend.discovery.cqs import (
    CQS,
    EnumPredicate,
    FilterAssignment,
    FlagPredicate,
    QueryMeta,
    RangePredicate,
    RegionPredicate,
    SortSpec,
    SpatialScope,
    canonical_key,
    cqs_equal,
    predicate_is_valid,
)


def _cqs(filters=None, sort=None, scope=None, meta=None) -> CQS:
    return CQS(
        filters=filters or {},
        sort=sort or SortSpec(key="pin", dir="asc"),
        scope=scope or SpatialScope(),
        meta=meta or QueryMeta(),
    )


# --- predicate validity (R1/R6) ---------------------------------------------


def test_empty_enum_and_region_are_invalid():
    assert not predicate_is_valid(EnumPredicate(values=[]))
    assert not predicate_is_valid(RegionPredicate(regions=[]))


def test_nonempty_enum_and_region_are_valid():
    assert predicate_is_valid(EnumPredicate(values=["residential"]))
    assert predicate_is_valid(RegionPredicate(regions=["ward:1"]))


def test_range_needs_at_least_one_bound():
    assert not predicate_is_valid(RangePredicate())
    assert predicate_is_valid(RangePredicate(min=100))
    assert predicate_is_valid(RangePredicate(max=100))


def test_inverted_range_is_valid_not_invalid():
    # min>max is honestly unsatisfiable, but a valid predicate (R6).
    assert predicate_is_valid(RangePredicate(min=500, max=100))


def test_flag_always_valid():
    assert predicate_is_valid(FlagPredicate(value=True))
    assert predicate_is_valid(FlagPredicate(value=False))


# --- canonical form + equality ----------------------------------------------


def test_canonical_key_is_byte_stable_across_calls():
    c = _cqs(filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))})
    assert canonical_key(c) == canonical_key(c)


def test_filter_order_does_not_affect_canonical_key():
    a = _cqs(filters={
        "tif": FilterAssignment(predicate=FlagPredicate(value=True)),
        "vacancy": FilterAssignment(predicate=FlagPredicate(value=True)),
    })
    b = _cqs(filters={
        "vacancy": FilterAssignment(predicate=FlagPredicate(value=True)),
        "tif": FilterAssignment(predicate=FlagPredicate(value=True)),
    })
    assert cqs_equal(a, b)


def test_enum_value_order_does_not_affect_equality():
    a = _cqs(filters={"land_use": FilterAssignment(predicate=EnumPredicate(values=["a", "b"]))})
    b = _cqs(filters={"land_use": FilterAssignment(predicate=EnumPredicate(values=["b", "a"]))})
    assert cqs_equal(a, b)


def test_equality_ignores_meta_and_source():
    a = _cqs(
        filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True), source="user")},
        meta=QueryMeta(topicId="t1", rawText="vacant", textResidual=["xyz"]),
    )
    b = _cqs(
        filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True), source="text")},
        meta=QueryMeta(),
    )
    assert cqs_equal(a, b)


def test_equality_distinguishes_predicate_value():
    a = _cqs(filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))})
    b = _cqs(filters={"tif": FilterAssignment(predicate=FlagPredicate(value=False))})
    assert not cqs_equal(a, b)


def test_equality_distinguishes_sort_and_scope():
    base = _cqs(filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))})
    diff_sort = _cqs(
        filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))},
        sort=SortSpec(key="pin", dir="desc"),
    )
    diff_scope = _cqs(
        filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))},
        scope=SpatialScope(mode="region", regions=["ward:1"]),
    )
    assert not cqs_equal(base, diff_sort)
    assert not cqs_equal(base, diff_scope)


def test_range_predicate_round_trips_through_discriminator():
    c = _cqs(filters={"lot_size": FilterAssignment(predicate=RangePredicate(min=2500))})
    assert isinstance(c.filters["lot_size"].predicate, RangePredicate)
