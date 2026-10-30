"""Lock the zone_definition payload shape served by /api/scorecard.

The endpoint serializes get_zone_definition() with dataclasses.asdict; the
frontend ZoningCard depends on these keys. The fallback chain (exact →
PD/PMD → prefix → unknown) must always yield a complete dict.
"""

from dataclasses import asdict

from backend.retrieval.zoning_definitions import get_zone_definition

EXPECTED_KEYS = {
    "zone_class", "name", "code_section", "far", "max_height",
    "lot_coverage", "min_lot_sqft", "min_lot_area_per_unit", "lot_area_note",
    "uses", "notes", "is_fallback",
}


def test_exact_match_serializes_full_standards():
    d = asdict(get_zone_definition("C1-2"))
    assert set(d) == EXPECTED_KEYS
    assert d["is_fallback"] is False
    assert d["far"] is not None
    assert d["name"]
    assert d["code_section"].startswith("§17")


def test_pd_fallback_serializes_with_advisory():
    d = asdict(get_zone_definition("PD 1234"))
    assert set(d) == EXPECTED_KEYS
    assert d["is_fallback"] is True
    assert d["far"] is None
    assert "planned development" in (d["uses"] + d["notes"]).lower()


def test_unknown_zone_serializes_safely():
    d = asdict(get_zone_definition("ZZ-9"))
    assert set(d) == EXPECTED_KEYS
    assert d["is_fallback"] is True
    assert d["notes"]


def test_per_unit_minimum_is_served_for_standard_districts_only():
    assert asdict(get_zone_definition("RM-4.5"))["min_lot_area_per_unit"] == 700
    assert asdict(get_zone_definition("B1-2"))["min_lot_area_per_unit"] == 1000
    assert asdict(get_zone_definition("PD 835"))["min_lot_area_per_unit"] is None
    assert asdict(get_zone_definition("ZZ-9"))["min_lot_area_per_unit"] is None
