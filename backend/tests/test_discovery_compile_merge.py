"""Step 6 tests — precedence merge, cleared-field rule, validity + validation drops (04.4)."""

from __future__ import annotations

from backend.discovery.compile_merge import merge
from backend.discovery.cqs import (
    CqsFragment,
    DroppedInvalid,
    EnumPredicate,
    FilterAssignment,
    FlagPredicate,
    QueryMeta,
    RangePredicate,
    SortSpec,
    SpatialScope,
)


def _frag(filters=None, source="user", **kw) -> CqsFragment:
    return CqsFragment(filters=filters or {}, **kw)


def _assign(pred, source="user"):
    return FilterAssignment(predicate=pred, source=source)


# --- precedence -------------------------------------------------------------


def test_user_overrides_text_for_same_filter():
    user = _frag({"land_use": _assign(EnumPredicate(values=["residential"]), "user")})
    text = _frag({"land_use": _assign(EnumPredicate(values=["commercial"]), "text")})
    cqs, dropped = merge(user, text)
    assert cqs.filters["land_use"].predicate == EnumPredicate(values=["residential"])
    assert cqs.filters["land_use"].source == "user"
    assert dropped == []


def test_text_fills_field_absent_from_user():
    user = _frag({"tif": _assign(FlagPredicate(value=True), "user")})
    text = _frag({"land_use": _assign(EnumPredicate(values=["multi_family"]), "text")})
    cqs, _ = merge(user, text)
    assert cqs.filters["land_use"].source == "text"
    assert cqs.filters["tif"].source == "user"


# --- cleared-field rule (no topic re-expansion) -----------------------------


def test_topic_id_is_telemetry_only_and_does_not_inject_filters():
    # User cleared everything a topic might have pre-filled; only topicId rides along.
    cqs, _ = merge(_frag({}), _frag({}), topic_id="vacant_multifamily")
    assert cqs.filters == {}
    assert cqs.meta.topicId == "vacant_multifamily"


# --- sort / scope / meta ----------------------------------------------------


def test_default_sort_when_no_override():
    cqs, _ = merge(_frag({}), _frag({}))
    assert cqs.sort == SortSpec(key="assessed_value", dir="asc")  # PR2 registry default
    assert cqs.scope == SpatialScope(mode="all")


def test_user_sort_and_scope_override():
    cqs, _ = merge(
        _frag({}), _frag({}),
        sort=SortSpec(key="lot_size", dir="desc"),
        scope=SpatialScope(mode="viewport", bbox=(-87.8, 41.8, -87.6, 42.0)),
    )
    assert cqs.sort == SortSpec(key="lot_size", dir="desc")
    assert cqs.scope.mode == "viewport"


def test_text_residual_carried_into_meta():
    text = _frag(meta=QueryMeta(rawText="waterfront tif", textResidual=["waterfront"]))
    text.filters["tif"] = _assign(FlagPredicate(value=True), "text")
    cqs, _ = merge(_frag({}), text)
    assert cqs.meta.rawText == "waterfront tif"
    assert cqs.meta.textResidual == ["waterfront"]


# --- R1 validity drops ------------------------------------------------------


def test_empty_enum_dropped_and_recorded():
    user = _frag({"land_use": _assign(EnumPredicate(values=[]))})
    cqs, dropped = merge(user, _frag({}))
    assert "land_use" not in cqs.filters
    assert dropped == [DroppedInvalid(filterId="land_use", reason="empty enum")]


def test_boundless_range_dropped():
    user = _frag({"lot_size": _assign(RangePredicate())})
    cqs, dropped = merge(user, _frag({}))
    assert "lot_size" not in cqs.filters
    assert [d.filterId for d in dropped] == ["lot_size"]


def test_inverted_range_is_kept_not_dropped():
    user = _frag({"lot_size": _assign(RangePredicate(min=9000, max=1000))})
    cqs, dropped = merge(user, _frag({}))
    assert cqs.filters["lot_size"].predicate == RangePredicate(min=9000, max=1000)
    assert dropped == []


def test_unknown_filter_id_dropped():
    user = _frag({"made_up": _assign(FlagPredicate(value=True))})
    cqs, dropped = merge(user, _frag({}))
    assert cqs.filters == {}
    assert [d.reason for d in dropped] == ["unknown filter"]


def test_kind_mismatch_dropped():
    # tif is a flag in the registry; sending a range for it is a kind mismatch.
    user = _frag({"tif": _assign(RangePredicate(min=1))})
    cqs, dropped = merge(user, _frag({}))
    assert "tif" not in cqs.filters
    assert [d.reason for d in dropped] == ["predicate kind mismatch"]


# --- compile-time validation: density_band needs zoning_group ---------------


def test_density_band_dropped_without_zoning_group():
    user = _frag({"density_band": _assign(RangePredicate(min=1.0))})
    cqs, dropped = merge(user, _frag({}))
    assert "density_band" not in cqs.filters
    assert any(d.filterId == "density_band" for d in dropped)


def test_density_band_kept_with_zoning_group():
    user = _frag({
        "zoning_group": _assign(EnumPredicate(values=["residential"])),
        "density_band": _assign(RangePredicate(min=1.0)),
    })
    cqs, dropped = merge(user, _frag({}))
    assert "density_band" in cqs.filters
    assert dropped == []
