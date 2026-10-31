"""WS5 PR1: the Predominance of the Block (606) rule in the unit-yield number (§17-2-0303-B.1).

In RS-3 inside the 606 district a two-unit building needs 1,500 sq ft of lot per unit.  The rule adds a path and
never caps the base rule; an unchecked overlay keeps the base number and says so; other districts are untouched.
The Profile, chat (ContextObject.unit_yield) and the $25 report read the same computed field."""

import pytest

from backend.models import (
    ContextObject,
    OverlayDistrict,
    PropertySummary,
    RegulatorySummary,
    ReportData,
    ZoningSummary,
)
from backend.report_builder import _compute_unit_yield
from backend.report_i18n import make_translator
from backend.retrieval.regulatory.overlay_facts import in_606_district
from backend.retrieval.zoning_definitions import max_units_by_lot_area

SD_606 = OverlayDistrict(layer_type="special_district", name="Predominance of the Block (606) District")


@pytest.mark.parametrize("lot, in_606, units, base, rule", [
    (2_999, True, 1, 1, "applied"),  # just under 3,000: 606 cannot make two
    (3_000, True, 2, 1, "applied"),  # exactly 3,000: two units
    (4_999, True, 2, 1, "applied"),
    (5_000, True, 2, 2, "applied"),  # the base already gives two
    (7_500, True, 3, 3, "applied"),  # never capped at two by the 606 rule
    (2_000, True, 0, 0, "applied"),  # the rule is for a two-unit building: it never makes a single unit
    (1_400, True, 0, 0, "applied"),
    (3_000, False, 1, 1, "not_in_district"),
    (3_000, None, 1, 1, "unchecked"),  # the check failed: the base number stands
])
def test_rs3_rule(lot, in_606, units, base, rule):
    uy = max_units_by_lot_area("RS-3", lot, in_606=in_606)
    assert (uy["units"], uy["base_units"], uy["rule_606"]) == (units, base, rule)


def test_arithmetic_shows_both_rules_when_606_raises_the_number():
    uy = max_units_by_lot_area("RS-3", 3_750, in_606=True)
    assert uy["arithmetic"].startswith("3,750 sq ft ÷ 2,500 sq ft per unit = 1.5 → 1 unit")
    assert "3,750 ÷ 1,500 = 2.5 → 2 units (§17-2-0303-B.1)" in uy["arithmetic"]
    assert uy["min_lot_area_per_unit"] == 1_500


def test_in_district_but_unchanged_says_so():
    uy = max_units_by_lot_area("RS-3", 7_500, in_606=True)
    assert "does not raise this number" in uy["arithmetic"] and uy["min_lot_area_per_unit"] == 2_500


def test_unchecked_says_the_check_failed():
    uy = max_units_by_lot_area("RS-3", 3_000, in_606=None)
    assert "could not check" in uy["caveat"]


@pytest.mark.parametrize("zone", ["RT-3.5", "RT-4", "RM-5", "B3-2", "RS-2"])
def test_other_districts_are_untouched(zone):
    a = max_units_by_lot_area(zone, 3_600, in_606=True)
    b = max_units_by_lot_area(zone, 3_600, in_606=False)
    c = max_units_by_lot_area(zone, 3_600, in_606=None)
    if a is None:
        assert b is None and c is None
        return
    assert a["units"] == b["units"] == c["units"] == a["base_units"]
    assert a["rule_606"] is None and a["arithmetic"] == b["arithmetic"] == c["arithmetic"]


def test_in_606_from_the_overlays():
    assert in_606_district(None) is None
    assert in_606_district(RegulatorySummary(overlays=[SD_606])) is True
    assert in_606_district(RegulatorySummary(overlays=[OverlayDistrict(layer_type="special_district", name="Other")])) is False
    assert in_606_district(RegulatorySummary()) is False
    assert in_606_district(RegulatorySummary(unchecked_overlays=["special_district"])) is None


def _ctx(regulatory, lot=3_750):
    return ContextObject(
        parcel_zoning=ZoningSummary(zone_class="RS-3", zone_type=1),
        property=PropertySummary(land_sqft=lot),
        regulatory=regulatory,
    )


def test_profile_chat_and_report_agree():
    ctx = _ctx(RegulatorySummary(overlays=[SD_606], in_special_district=True))
    assert ctx.unit_yield["units"] == 2  # Profile JSON and chat context both serialize this field
    assert ctx.model_dump()["unit_yield"]["units"] == 2
    report = ReportData(context=ctx)
    uy = _compute_unit_yield(report)
    assert uy["units"] == 2 and uy["mla_per_unit"] == 1_500 and uy["raised_by_606"] is True


def test_no_regulatory_lookup_is_unchecked_not_absent():
    """A chat turn that skipped the regulatory domain must not read as 'not in the district'."""
    assert _ctx(None).unit_yield["rule_606"] == "unchecked"
    assert _ctx(None).unit_yield["units"] == 1


@pytest.mark.parametrize("lang", ["en", "es"])
def test_report_sentences_exist(lang):
    t = make_translator(lang)
    assert "1,500" in t("dev.unit_capacity_606") and "606" in t("dev.unit_capacity_606_unchecked")
