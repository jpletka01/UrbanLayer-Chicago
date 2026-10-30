"""F7: name the overlays and say what they require.

Kit 2026-10-01: the Profile showed the 606 district as a generic "Special Districts",
said "ADU eligible" for any parcel the ADU layer hit and never named Zone 10 or its
limits (P6), linked nothing for PD 835 (P4), and described a landmark's consequence
as "expect design review" when §2-120-740 requires the Commission's written approval
(P5). Every statement is pinned to the ingested code text; where the code doesn't say,
the detail is empty."""

import json
from pathlib import Path

import pytest

from backend.models import ContextObject, OverlayDistrict, RegulatorySummary, ZoningSummary
from backend.retrieval.regulatory import _build_summary
from backend.retrieval.regulatory.overlay_facts import describe_overlay
from backend.retrieval.zoning_definitions import adu_status

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"


def _text(section_id: str) -> str:
    path = SECTIONS / f"{section_id}.json"
    if not path.exists():
        pytest.skip(f"ordinance corpus not present: {path}")
    d = json.loads(path.read_text())
    return " ".join(d["body_paragraphs"])


# --- naming and detail from real layer attributes (queried 2026-10-02) --------------------

SD_606 = {"SD_NAME": "Predominance of the Block (606) District", "DATE_EFFECT": 1611705600000,
          "LINK": "https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-53035"}
ADU_Z10 = {"ADU_AREA": "1, 2", "ZONE": "Zone 10", "TEXT": "Annual Limits, Owner Occupancy Limits"}
HD_56 = {"NUMBER_": "HD-56", "NAME": "Milwaukee Avenue District", "LANDMARK": "Y"}


def test_606_district_is_named_linked_and_scoped():
    f = describe_overlay("special_district", SD_606)
    assert f["name"] == "Predominance of the Block (606) District"
    assert f["link"].startswith("https://codelibrary.amlegal.com/")
    assert "RS-3 and RT-3.5 parcels only" in f["detail"] and "1,500 sq ft" in f["detail"]
    assert "does not change the density of other districts" in f["detail"]


def test_606_statements_match_the_code():
    t = _text("17-7-0590")
    assert "all parcels zoned RS3 and RT3.5" in t  # 17-7-0591
    assert "may be reduced to 1,500 square feet" in _text("17-2-0300")  # 17-2-0303-B.1


def test_unknown_special_district_gets_a_name_but_no_invented_effect():
    f = describe_overlay("special_district", {"SD_NAME": "Some Other District", "LINK": "https://x"})
    assert f["name"] == "Some Other District" and "See the linked code section" in f["detail"]
    assert describe_overlay("special_district", {}) == {"name": None, "detail": None, "link": None}


def test_planned_development_is_named_and_links_the_ordinance_pdf():
    f = describe_overlay("planned_development", {"PD_NUM": 835})
    assert f["name"] == "Planned Development 835"
    assert f["link"] == "https://gisapps.chicago.gov/gisimages/zoning_pds/PD835.pdf"
    assert "PD ordinance" in f["detail"] and "not from Title 17" in f["detail"]
    assert describe_overlay("planned_development", {"PD_NUM": 835.0})["link"].endswith("PD835.pdf")
    assert describe_overlay("planned_development", {})["link"] is None


def test_landmark_requires_commission_approval_not_design_review():
    f = describe_overlay("landmark_building", {"NAME": "One North LaSalle Building", "LANDMARK": "4/16/1996"})
    assert f["name"] == "One North LaSalle Building"
    assert "designated 4/16/1996" in f["detail"]
    assert "written approval" in f["detail"] and "§2-120-740" in f["detail"]
    assert "design review" not in f["detail"].lower()
    d = describe_overlay("historic_district", HD_56)
    assert d["name"] == "Milwaukee Avenue District (HD-56)" and "§2-120-740" in d["detail"]


def test_only_a_chicago_landmark_district_gets_the_permit_statement():
    plain = describe_overlay("historic_district", {"NAME": "Some Historic District", "NUMBER_": "X", "LANDMARK": " "})
    assert plain["detail"] is None
    assert describe_overlay("landmark_district", {"NAME": "Pullman"})["detail"] is not None


def test_landmark_permit_statement_matches_the_code():
    t = _text("2-120-740")
    assert "without the written approval of the commission" in t
    assert "landmark district" in t and "demolition" in t and "addition" in t


def test_adu_zone_and_limits_are_named():
    f = describe_overlay("adu_area", ADU_Z10)
    assert f["name"] == "ADU-Allowed RS Area — Zone 10"
    assert "Annual Limits, Owner Occupancy Limits" in f["detail"] and "§17-7-0574" in f["detail"]


# --- carried into the regulatory summary ---------------------------------------------------------

def test_summary_overlays_carry_name_detail_and_link():
    hits = [(9, SD_606), (17, ADU_Z10), (2, {"PD_NUM": 835}), (5, {"NAME": "One North LaSalle Building"})]
    s = _build_summary(hits, None, [])
    by = {o.layer_type: o for o in s.overlays}
    assert by["special_district"].name == "Predominance of the Block (606) District"
    assert by["special_district"].link.startswith("https://codelibrary")
    assert by["planned_development"].link.endswith("PD835.pdf")
    assert by["landmark_building"].detail.startswith("Individual Chicago Landmark")
    assert by["adu_area"].name.endswith("Zone 10")
    assert s.in_special_district and s.in_adu_area and s.in_planned_development


def test_layers_without_special_facts_keep_their_old_labels():
    s = _build_summary([(20, {})], None, [])
    assert s.overlays[0].name == "Affordable Requirements Ordinance Zones"
    assert s.overlays[0].detail is None and s.overlays[0].link is None


# --- ADU status is zone-aware, pinned to the use tables --------------------------------------------

def test_adu_rs_in_a_zone_names_the_zone_and_its_limits():
    s = adu_status("RS-3", True, "ADU-Allowed RS Area — Zone 10", "Limitations: Annual Limits, Owner Occupancy Limits (§17-7-0573, §17-7-0574).")
    assert s["status"] == "allowed_with_limits"
    assert "Zone 10" in s["note"] and "Owner Occupancy Limits" in s["note"] and "§17-7-0570" in s["note"]


def test_adu_rs_outside_a_zone_is_not_allowed():
    s = adu_status("RS-2", False)
    assert s["status"] == "not_allowed" and "only inside an ADU-Allowed RS Area" in s["note"]


@pytest.mark.parametrize("zone", ["RT-4", "RT-3.5", "RM-4.5", "RM-6", "B1-2", "B3-2", "C1-3", "C2-2"])
def test_adu_by_right_outside_rs_whatever_the_layer_says(zone):
    assert adu_status(zone, True, "ADU-Allowed RS Area — Zone 8", "x")["status"] == "allowed_by_right"
    assert adu_status(zone, False)["status"] == "allowed_by_right"


@pytest.mark.parametrize("zone", ["C3-2", "M1-2", "DX-7", "PD 835", "POS-1", "", None])
def test_adu_silent_where_the_use_tables_do_not_say(zone):
    assert adu_status(zone, True, "x", "y") is None


def test_adu_statuses_match_the_use_tables():
    r = json.loads((SECTIONS / "17-2-0200.json").read_text()) if (SECTIONS / "17-2-0200.json").exists() else pytest.skip("no corpus")
    rows = {row[1]: row for t in r["tables"] for row in t["data_rows"] if len(row) > 9 and row[1] in ("Coach House", "Conversion Unit")}
    for name in ("Coach House", "Conversion Unit"):
        rs, rt = rows[name][2:5], rows[name][5:10]
        assert all(c.startswith("P/-") for c in rs)  # RS-1..3: only with the footnoted ADU Area
        assert all(c == "P" for c in rt)  # RT/RM: by right
    assert "only permitted by right within RS zoning districts that are located within an Additional Dwelling Unit-Allowed RS Area" in " ".join(
        c for t in r["tables"] for row in t["data_rows"] for c in row[:1] if c.startswith("*")
    )
    bc = json.loads((SECTIONS / "17-3-0200.json").read_text())
    ch = [row for t in bc["tables"] for row in t["data_rows"] if len(row) > 3 and row[1] == "Coach House"][0]
    assert ch[2:7] == ["P"] * 5 and ch[7] == "-"  # B1-C2 by right, C3 not


# --- carried to the Profile and chat -------------------------------------------------------------------

def _ctx(zone: str, overlays: list[OverlayDistrict]) -> ContextObject:
    return ContextObject(
        parcel_zoning=ZoningSummary(zone_class=zone),
        regulatory=RegulatorySummary(in_adu_area=any(o.layer_type == "adu_area" for o in overlays), overlays=overlays),
    )


def test_context_adu_for_the_kit_parcels():
    z10 = OverlayDistrict(layer_type="adu_area", name="ADU-Allowed RS Area — Zone 10",
                          detail="Limitations: Annual Limits, Owner Occupancy Limits (§17-7-0573, §17-7-0574).")
    p6 = _ctx("RS-3", [z10]).model_dump(exclude_none=True)["adu"]
    assert p6["status"] == "allowed_with_limits" and "Owner Occupancy" in p6["note"]
    assert _ctx("RT-4", [z10]).adu["status"] == "allowed_by_right"  # P7: the layer artifact is dropped
    assert _ctx("RS-2", []).adu["status"] == "not_allowed"  # P1
    assert ContextObject().adu is None


def test_prompt_rule_35_forbids_design_review_and_unscoped_606_claims():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("35. OVERLAYS: NAME THEM")
    rule = SYNTHESIZER_SYSTEM[i : i + 2600]
    assert 'never "design review"' in rule and "applies only to RS-3 and RT-3.5 parcels" in rule
    assert "PD link" in rule and "ADU-eligible" in rule
