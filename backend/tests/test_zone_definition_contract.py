"""Lock the zone_definition payload shape served by /api/scorecard.

The endpoint serializes get_zone_definition() with dataclasses.asdict; the
frontend ZoningCard depends on these keys. The fallback chain (exact →
PD/PMD → prefix → unknown) must always yield a complete dict.
"""

from dataclasses import asdict

from backend.retrieval.zoning_definitions import get_zone_definition

EXPECTED_KEYS = {
    "zone_class", "name", "code_section", "far", "max_height",
    "lot_coverage", "min_lot_sqft", "uses", "notes", "is_fallback",
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
