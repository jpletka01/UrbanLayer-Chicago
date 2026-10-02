"""F3: the binding number — minimum lot area per unit and the unit yield it gives.

Kit 2026-10-01: the Profile never showed RM-4.5's 700 sq ft per unit, and chat
filled it in from memory (1,000 → "3 units" instead of 4; FAR 2.2 instead of 1.7).
These tests pin the data to the ordinance text already in the repo and check that
the standards reach chat on every parcel-resolved turn, not only on a handoff."""

import json
import re
from pathlib import Path

import pytest

from backend.main import _ensure_zone_definition
from backend.models import ContextObject, PropertySummary, ZoningSummary
from backend.retrieval.zoning_definitions import (
    ZONE_CLASS_DATA,
    get_zone_definition,
    max_units_by_lot_area,
    min_lot_area_per_unit,
)

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"
USE_COLUMNS = ["RS-1", "RS-2", "RS-3", "RT-3.5", "RT-4", "RM-4.5", "RM-5/5.5", "RM-6/6.5"]


def _use_table() -> dict[str, list[str]]:
    path = SECTIONS / "17-2-0200.json"
    if not path.exists():
        pytest.skip("ordinance corpus not present")
    rows: dict[str, list[str]] = {}
    for t in json.loads(path.read_text())["tables"]:
        for r in t["data_rows"]:
            if len(r) > 9 and r[1] in ("Detached House", "Two-Flat", "Townhouse", "Multi-Unit (3+ units) Residential"):
                rows[r[1]] = r[2:10]
    return rows


def _col(zone: str) -> int:
    for i, c in enumerate(USE_COLUMNS):
        if zone == c or zone in c.split("/") or (c.startswith("RM-5") and zone in ("RM-5", "RM-5.5")) or (c.startswith("RM-6") and zone in ("RM-6", "RM-6.5")):
            return i
    raise KeyError(zone)


# --- uses text is pinned to the use table (§17-2-0207) ------------------------------

@pytest.mark.parametrize("zone", [z for z in ZONE_CLASS_DATA if z.startswith(("RS-", "RT-", "RM-"))])
def test_residential_uses_text_matches_the_use_table(zone):
    table = _use_table()
    uses = ZONE_CLASS_DATA[zone].uses.lower()
    c = _col(zone)
    for row, term in (("Two-Flat", "two-flat"), ("Multi-Unit (3+ units) Residential", "multi-unit")):
        allowed = table[row][c].startswith("P")
        assert (term in uses) == allowed, (zone, row, table[row][c], uses)


def test_the_two_misses_the_kit_found_are_fixed():
    assert "two-flat" in get_zone_definition("RS-3").uses.lower()  # P6: a 606 two-flat
    assert "multi-unit" in get_zone_definition("RT-4").uses.lower()  # P7: RT-4 multi-unit
    assert "two-flat" not in get_zone_definition("RS-2").uses.lower()  # P1: still not allowed


# --- minimum lot area per unit ------------------------------------------------------------

def test_zone_definition_carries_the_parity_tested_per_unit_minimum():
    for zone in ZONE_CLASS_DATA:
        assert get_zone_definition(zone).min_lot_area_per_unit == min_lot_area_per_unit(zone)
    assert get_zone_definition("RM-4.5").min_lot_area_per_unit == 700


def test_rs3_note_carries_the_606_exemption_pinned_to_the_code():
    note = get_zone_definition("RS-3").lot_area_note
    assert "1,500" in note and "Predominance of the Block (606)" in note and "two-unit" in note
    path = SECTIONS / "17-2-0300.json"
    if path.exists():
        text = " ".join(json.loads(path.read_text())["body_paragraphs"])
        i = text.index("17-2-0303-B")
        para = text[i : i + 700]
        assert "RS3" in para and "1,500 square feet" in para and "only allow for the establishment of a two-unit building" in para
    assert get_zone_definition("RS-2").lot_area_note == ""


# --- unit yield -------------------------------------------------------------------------------

def test_rm45_yield_is_four_not_three_and_never_six():
    y = max_units_by_lot_area("RM-4.5", 3191)
    assert y["units"] == 4 and y["min_lot_area_per_unit"] == 700
    assert y["arithmetic"] == "3,191 sq ft ÷ 700 sq ft per unit = 4.6 → 4 units"
    assert "Lot area per unit only" in y["caveat"]
    assert max_units_by_lot_area("RM-4.5", 3154)["units"] == 4  # the City's estimate for the kit parcel
    assert max_units_by_lot_area("RM-4.5", 4200)["units"] == 6  # six would need 4,200 sq ft


def test_yield_floors_and_handles_a_lot_below_one_unit():
    assert max_units_by_lot_area("RT-4", 1999)["units"] == 1
    y = max_units_by_lot_area("RS-2", 4000)
    assert y["units"] == 0 and "0 units" in y["arithmetic"]


@pytest.mark.parametrize("zone,lot", [("C3-2", 5000), ("M1-2", 9000), ("PD 835", 90000), ("DS-3", 5000), ("ZZ-9", 3000), (None, 3000), ("RM-4.5", None), ("RM-4.5", 0)])
def test_no_yield_without_a_per_unit_minimum_or_a_lot_area(zone, lot):
    assert max_units_by_lot_area(zone, lot) is None


def test_rs3_yield_mentions_the_606_second_unit():
    assert "606" in max_units_by_lot_area("RS-3", 3000)["caveat"]


# --- carried to the Profile and to chat ---------------------------------------------------------

def _ctx(zone: str, land: int | None) -> ContextObject:
    return ContextObject(
        parcel_zoning=ZoningSummary(zone_class=zone, zone_type=4),
        property=PropertySummary(land_sqft=land),
    )


def test_context_object_derives_unit_yield_on_every_path():
    dumped = _ctx("RM-4.5", 3191).model_dump(exclude_none=True)
    assert dumped["unit_yield"]["units"] == 4
    assert json.loads(_ctx("RM-4.5", 3191).model_dump_json())["unit_yield"]["min_lot_area_per_unit"] == 700
    ctx = ContextObject()  # a handoff grafts these in after construction
    ctx.parcel_zoning = ZoningSummary(zone_class="RM-4.5", zone_type=4)
    ctx.property = PropertySummary(land_sqft=3191)
    assert ctx.unit_yield["units"] == 4


def test_no_yield_without_zoning_or_lot_area():
    assert ContextObject().unit_yield is None
    assert _ctx("RM-4.5", None).unit_yield is None
    assert _ctx("C3-2", 5000).unit_yield is None


def test_cold_chat_gets_the_zone_table_but_a_handoff_keeps_its_own():
    ctx = _ctx("RM-4.5", 3191)
    assert ctx.zone_definition is None
    _ensure_zone_definition(ctx)
    assert ctx.zone_definition["far"] == 1.7 and ctx.zone_definition["min_lot_area_per_unit"] == 700
    handed = _ctx("RM-4.5", 3191)
    handed.zone_definition = {"zone_class": "RM-4.5", "far": 9.9}
    _ensure_zone_definition(handed)
    assert handed.zone_definition["far"] == 9.9
    bare = ContextObject()
    _ensure_zone_definition(bare)
    assert bare.zone_definition is None


def test_prompt_rule_forbids_recalling_numbers_and_leaking_field_names():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("33. NUMERIC STANDARDS")
    rule = SYNTHESIZER_SYSTEM[i : i + 2200]
    assert "NEVER recall it from general knowledge" in rule
    assert "unit_yield" in rule and "arithmetic" in rule
    assert re.search(r"Never name context fields", rule)
