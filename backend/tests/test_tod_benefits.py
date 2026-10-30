"""Transit-served benefits: parking relief everywhere, density bonuses only in
dash-3 districts (kit 2026-10-01 caught "...and a density bonus" on B1-2, RS-3
and RT-4 parcels). The rule is pinned to the ordinance text already ingested
under ingestion/data/sections, so a code change shows up here, not in a customer's
feasibility screen."""

import json
import re
from pathlib import Path

import pytest

from backend.models import ContextObject, RegulatorySummary, ZoningSummary
from backend.retrieval.zoning_definitions import tod_benefits

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"
CTA = ("tod_cta",)


def _text(section_id: str) -> str:
    path = SECTIONS / f"{section_id}.json"
    if not path.exists():
        pytest.skip(f"ordinance corpus not present: {path}")
    return " ".join(json.loads(path.read_text())["body_paragraphs"])


# --- the rule ------------------------------------------------------------------

@pytest.mark.parametrize("zone", ["B1-2", "B3-2", "C1-2", "C2-5", "RS-3", "RT-4", "RM-4.5", "M1-2", "DX-7", "DC-16", "B3-1.5"])
def test_no_density_bonus_outside_dash_3(zone):
    b = tod_benefits(zone, True, CTA)
    assert b["density_bonus_eligible"] is False and b["entitlement_required"] is False
    assert b["parking_relief"] is True
    assert "No density, FAR or height bonus" in b["note"]


@pytest.mark.parametrize("zone", ["B1-3", "B2-3", "B3-3", "C1-3", "C2-3", "DX-3", "DR-3", "DS-3"])
def test_dash_3_is_eligible_but_only_with_an_entitlement(zone):
    b = tod_benefits(zone, True, CTA)
    assert b["density_bonus_eligible"] is True and b["entitlement_required"] is True
    assert "Type 1 map amendment" in b["note"] and "ARO" in b["note"]


def test_not_transit_served_returns_nothing():
    assert tod_benefits("B3-3", False, CTA) is None


@pytest.mark.parametrize(
    "zone,layers,pct",
    [("B1-2", ("tod_cta",), 100), ("RS-3", ("tod_metra",), 50), ("DX-7", ("tod_cta",), 50), ("B1-2", (), None)],
)
def test_parking_reduction_percent(zone, layers, pct):
    assert tod_benefits(zone, True, layers)["parking_max_reduction_pct"] == pct


def test_planned_development_defers_to_its_ordinance():
    b = tod_benefits("PD 835", True, CTA)
    assert b["parking_relief"] is None and b["density_bonus_eligible"] is False
    assert "PD ordinance governs" in b["note"]


def test_unknown_zone_never_claims_a_bonus():
    for z in (None, "", "weird"):
        assert tod_benefits(z, True, CTA)["density_bonus_eligible"] is False


# --- pinned to the ordinance text --------------------------------------------------

def test_bonus_sections_name_only_dash_3_districts():
    bc = _text("17-3-0400")
    for sub in ("17-3-0402-B", "17-3-0403-B", "17-3-0408-B"):
        i = bc.index(sub)
        para = bc[i : i + 700]
        assert "B-3 and C-3 districts" in para, sub
        assert re.search(r"Type (I|1) Zoning Map Amendment", para), sub
    d = _text("17-4-0400")
    assert "Projects in D-3 districts" in d


def test_parking_relief_rule_matches_the_code():
    text = _text("17-10-0100")
    i = text.index("17-10-0102-B")
    para = text[i : i + 1800]
    assert "In all districts except D districts" in para and "up to 100 percent" in para
    assert "In D districts" in para and "up to 50 percent" in para


# --- carried to the Profile and to chat ----------------------------------------------

def _ctx(zone: str, tod: bool = True) -> ContextObject:
    overlays = [{"layer_type": "tod_cta", "name": "TOD (CTA)", "description": "x"}] if tod else []
    return ContextObject(
        parcel_zoning=ZoningSummary(zone_class=zone, zone_type=1),
        regulatory=RegulatorySummary(in_tod_area=tod, overlays=overlays),
    )


def test_context_object_derives_tod_benefits_on_every_path():
    dumped = _ctx("B1-2").model_dump(exclude_none=True)
    assert dumped["tod_benefits"]["density_bonus_eligible"] is False
    assert dumped["tod_benefits"]["parking_max_reduction_pct"] == 100
    assert "tod_benefits" in json.loads(_ctx("B3-3").model_dump_json())  # what the synthesizer serializes
    assert _ctx("B3-3").tod_benefits["density_bonus_eligible"] is True
    # a Profile->chat handoff grafts zoning in AFTER construction; still correct
    ctx = ContextObject()
    ctx.parcel_zoning = ZoningSummary(zone_class="RT-4", zone_type=4)
    ctx.regulatory = RegulatorySummary(in_tod_area=True, overlays=[])
    assert ctx.tod_benefits["density_bonus_eligible"] is False


def test_no_tod_no_benefits():
    assert _ctx("B1-2", tod=False).tod_benefits is None
    assert ContextObject().tod_benefits is None


def test_prompt_rule_forbids_unqualified_density_bonus_claims():
    from backend.prompts import SYNTHESIZER_SYSTEM

    assert "density_bonus_eligible" in SYNTHESIZER_SYSTEM and "DASH-3" in SYNTHESIZER_SYSTEM
    assert "allows density and parking bonuses near transit" not in SYNTHESIZER_SYSTEM
