"""Step 5 tests — deterministic text compiler (04.3). Table-driven: string → fragment."""

from __future__ import annotations

import pytest

from backend.discovery.compile_text import parse
from backend.discovery.cqs import EnumPredicate, FlagPredicate, RangePredicate


def _pred(frag, fid):
    return frag.filters[fid].predicate


# --- determinism + totality -------------------------------------------------


@pytest.mark.parametrize("text", [
    "", "   ", "vacant multifamily tif built after 1990 at least 6 units",
    "completely unmappable gibberish words",
])
def test_parse_is_deterministic(text):
    assert parse(text).model_dump() == parse(text).model_dump()


def test_empty_text_yields_empty_fragment():
    frag = parse("")
    assert frag.filters == {}
    assert frag.meta.textResidual == []


def test_every_assignment_is_tagged_source_text():
    frag = parse("vacant multifamily tif")
    assert frag.filters
    assert all(a.source == "text" for a in frag.filters.values())


# --- flags ------------------------------------------------------------------


def test_flag_phrases():
    frag = parse("find tif opportunity zone enterprise zone brownfield parcels")
    for fid in ("tif", "opportunity_zone", "enterprise_zone", "brownfield"):
        assert _pred(frag, fid) == FlagPredicate(value=True)


def test_vacant_maps_to_vacancy_flag_not_land_use():
    frag = parse("show me vacant parcels")
    assert _pred(frag, "vacancy") == FlagPredicate(value=True)
    assert "land_use" not in frag.filters


def test_longest_phrase_wins_vacant_lot():
    # "vacant lot" is consumed as one span; the inner "vacant" must not double-emit.
    frag = parse("vacant lot")
    assert _pred(frag, "vacancy") == FlagPredicate(value=True)
    assert frag.meta.textResidual == []


# --- enums ------------------------------------------------------------------


def test_enum_land_use_synonyms():
    assert _pred(parse("multifamily"), "land_use") == EnumPredicate(values=["multi_family"])
    assert _pred(parse("multi-family"), "land_use") == EnumPredicate(values=["multi_family"])
    assert _pred(parse("warehouse"), "land_use") == EnumPredicate(values=["industrial"])


def test_enum_or_merge_within_filter():
    frag = parse("multifamily and mixed use")
    assert _pred(frag, "land_use") == EnumPredicate(values=["mixed_use", "multi_family"])


def test_zoning_group_requires_qualifier():
    # bare "residential" is ambiguous → residual, never an assignment
    bare = parse("residential")
    assert bare.filters == {}
    assert "residential" in bare.meta.textResidual
    # qualified form maps to zoning_group
    assert _pred(parse("zoned residential"), "zoning_group") == EnumPredicate(values=["residential"])


# --- range grammar ----------------------------------------------------------


def test_year_built_after_before_between():
    assert _pred(parse("built after 1990"), "year_built") == RangePredicate(min=1990)
    assert _pred(parse("built before 1970"), "year_built") == RangePredicate(max=1970)
    assert _pred(parse("built between 1950 and 1980"), "year_built") == RangePredicate(min=1950, max=1980)


def test_units_min_and_max():
    assert _pred(parse("at least 6 units"), "units") == RangePredicate(min=6)
    assert _pred(parse("6+ units"), "units") == RangePredicate(min=6)
    assert _pred(parse("under 20 units"), "units") == RangePredicate(max=20)


def test_units_min_and_max_merge_from_two_phrases():
    frag = parse("at least 6 units and under 20 units")
    assert _pred(frag, "units") == RangePredicate(min=6, max=20)


def test_lot_size_requires_sqft_unit():
    assert _pred(parse("lot over 5,000 sqft"), "lot_size") == RangePredicate(min=5000)
    assert _pred(parse("lot under 10000 sf"), "lot_size") == RangePredicate(max=10000)
    # a bare number with no sqft unit is NOT a lot size → residual
    assert "lot_size" not in parse("5000").filters


# --- residual ---------------------------------------------------------------


def test_unmapped_tokens_go_to_residual_and_do_not_constrain():
    frag = parse("waterfront tif charming")
    assert _pred(frag, "tif") == FlagPredicate(value=True)
    assert frag.meta.textResidual == ["waterfront", "charming"]


def test_residual_excludes_consumed_phrase_fragments():
    frag = parse("multifamily built after 1990")
    # no stray "multifamily"/"built"/"1990" tokens leak into residual
    assert frag.meta.textResidual == []


def test_raw_text_preserved_in_meta():
    assert parse("Vacant TIF").meta.rawText == "Vacant TIF"


# --- combined ---------------------------------------------------------------


def test_combined_query_compiles_all_parts():
    frag = parse("vacant multifamily in a tif zone, built after 1990, at least 6 units")
    assert _pred(frag, "vacancy") == FlagPredicate(value=True)
    assert _pred(frag, "land_use") == EnumPredicate(values=["multi_family"])
    assert _pred(frag, "tif") == FlagPredicate(value=True)
    assert _pred(frag, "year_built") == RangePredicate(min=1990)
    assert _pred(frag, "units") == RangePredicate(min=6)
