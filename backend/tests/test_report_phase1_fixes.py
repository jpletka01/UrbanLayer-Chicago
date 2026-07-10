"""Regression tests for Phase 1 report-viability fixes (R1–R4).

These guard the pipeline bugs surfaced by the V6 real-data audit so they cannot
silently return. See claude-context/guides/report-v6-execution-plan.md.
"""

import pytest

from backend.zoning_extract import standards_from_definitions


# --- R1: zoning definitions fallback ---------------------------------------

def test_r1_definitions_fallback_rm6():
    """RM-6 must resolve to authoritative base-district standards (FAR 4.4).

    Table 17-2-0305 sets NO numeric height cap for RM-6 (tall buildings go
    through PD review) and Title 17 has no base-district lot-coverage standard
    — both previously carried fabricated values (70 ft / 60%; 2026-07-06 audit,
    see test_zoning_ordinance_parity.py).
    """
    s = standards_from_definitions("RM-6")
    assert s is not None
    assert s.far == 4.4
    assert s.max_height_ft is None
    assert s.lot_coverage_pct is None
    assert s.min_lot_area_sqft == 1650
    assert s.min_lot_area_per_unit_sqft == 300
    assert s.extraction_confidence == "definitions"
    assert s.permitted_uses  # residential uses, not commercial/manufacturing
    assert any("Height:" in n for n in s.notes)  # the no-cap explanation surfaces


def test_r1_definitions_fallback_commercial():
    """B3-2 resolves to its own FAR, not a residential/manufacturing value."""
    s = standards_from_definitions("B3-2")
    assert s is not None
    assert s.far == 2.2


@pytest.mark.parametrize("zone", ["PD 100", "PMD 9", "ZZ-99", ""])
def test_r1_definitions_fallback_unknown_returns_none(zone):
    """Unknown / planned-development zones return None so the raw-code path stays."""
    assert standards_from_definitions(zone) is None


# --- R3: comparable-sales class derivation ---------------------------------

def test_r3_comp_class_prefix():
    from backend.report_builder import _comp_class_prefix

    # Marketable subject uses its own class family.
    assert _comp_class_prefix("205", "RM-5") == "2"
    assert _comp_class_prefix("517", "B3-2") == "5"
    # Non-marketable (exempt) subject derives from zoning.
    assert _comp_class_prefix("EX", "RM-6") == "2"
    assert _comp_class_prefix("EX", "B3-2") == "5"
    # No signal at all → residential default.
    assert _comp_class_prefix(None, None) == "2"


# --- R4: nearby-development currency formatting -----------------------------

def test_r4_fmt_money():
    from backend.report_builder import _fmt_money

    assert _fmt_money(3_987_000) == "$4.0M"   # was the "$3987K" bug
    assert _fmt_money(35_900_000) == "$35.9M"
    assert _fmt_money(750_000) == "$750K"
    assert _fmt_money(120_000) == "$120K"
