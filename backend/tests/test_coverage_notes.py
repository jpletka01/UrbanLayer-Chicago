"""V4: "what this page does not cover" - stated per parcel, each note pinned to a source.

A screening page that never says where it stops reads as a determination. Statements
about the code are checked against the ingested text; the City's letter terms are the
Office of the Zoning Administrator's published ones (checked 2026-09-30)."""

import json
from pathlib import Path

import pytest

from backend.models import (
    ContextObject, NeighborhoodSummary, OverlayDistrict, ParcelFlags, PropertySummary,
    RegulatorySummary, WardInfo, ZoningSummary,
)
from backend.retrieval.coverage_notes import OFFICIAL_LETTER_DAYS, OFFICIAL_LETTER_FEE, build_coverage_notes

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"
WARD = WardInfo(ward=32, alderman="Scott Waguespack", phone="(773) 248-1330", website="https://ward32.org")


def _text(section_file: str) -> str:
    path = SECTIONS / f"{section_file}.json"
    if not path.exists():
        pytest.skip("ordinance corpus not present")
    return " ".join(json.loads(path.read_text())["body_paragraphs"])


def _ctx(zone="RT-4", *, overlays=(), flags=None, ward=WARD, **zkw) -> ContextObject:
    return ContextObject(
        parcel_zoning=ZoningSummary(zone_class=zone, **zkw),
        regulatory=RegulatorySummary(overlays=list(overlays)),
        property=PropertySummary(pin14="14291230290000", flags=flags),
        neighborhood=NeighborhoodSummary(ward=ward) if ward else None,
    )


def _ids(ctx: ContextObject) -> list[str]:
    return [n["id"] for n in ctx.coverage_notes]


# --- every parcel gets the general notes, last --------------------------------------------

def test_every_parcel_gets_the_general_notes_after_the_parcel_specific_ones():
    ids = _ids(_ctx())
    assert ids == ["aldermanic", "map_lag", "code_vintage", "official_letter"]
    notes = _ctx().coverage_notes
    assert all(n["applies"] == "general" for n in notes)


def test_the_official_letter_note_says_this_is_not_a_determination_and_who_issues_one():
    n = next(x for x in _ctx().coverage_notes if x["id"] == "official_letter")
    assert "not a zoning determination" in n["text"]
    assert f"${OFFICIAL_LETTER_FEE}" in n["text"] and f"{OFFICIAL_LETTER_DAYS} days" in n["text"]
    assert n["link"].startswith("https://www.chicago.gov/") and n["params"]["checked"] == "2026-09-30"


def test_no_notes_without_a_resolved_district():
    assert ContextObject().coverage_notes is None


def test_the_alderman_note_names_the_ward_and_degrades_without_one():
    with_ward = next(n for n in _ctx().coverage_notes if n["id"] == "aldermanic")
    assert "Ward 32: Ald. Scott Waguespack, (773) 248-1330." in with_ward["text"] and with_ward["link"] == "https://ward32.org"
    without = next(n for n in _ctx(ward=None).coverage_notes if n["id"] == "aldermanic")
    assert "Ward" not in without["text"] and without["params"]["ward"] is None
    assert "cannot assess" in without["text"]


def test_alderman_notice_statements_match_the_code():
    assert "Alderman of the ward" in _text("17-13-0100")  # special use / administrative adjustment notice
    assert "notify the Alderman of the ward" in _text("17-13-0300")  # Type 1 map amendment community meeting
    assert "notify the Alderman of the ward" in _text("17-13-0600")  # Planned Development community meeting


def test_the_vintage_note_follows_the_codes_current_through_date():
    n = next(x for x in _ctx().coverage_notes if x["id"] == "code_vintage")
    assert "2026-03-18" in n["text"] and n["params"]["date"] == "2026-03-18"


# --- parcel-specific notes ---------------------------------------------------------------------------

def test_a_planned_development_says_the_base_numbers_do_not_apply_and_links_the_ordinance():
    pd = OverlayDistrict(layer_type="planned_development", name="Planned Development 835", link="https://gisapps.chicago.gov/gisimages/zoning_pds/PD835.pdf")
    n = next(x for x in _ctx("PD 835", overlays=[pd]).coverage_notes if x["id"] == "planned_development")
    assert n["applies"] == "parcel" and "Planned Development 835" in n["text"] and "do not apply" in n["text"]
    assert n["link"].endswith("PD835.pdf")
    # a PD district without the overlay row still gets the note (no link)
    bare = next(x for x in _ctx("PD 12").coverage_notes if x["id"] == "planned_development")
    assert bare["link"] is None and "PD 12" in bare["text"]


def test_a_landmark_says_written_approval_is_required_and_not_assessed_here():
    lm = OverlayDistrict(layer_type="landmark_building", name="Noel State Bank",
                         detail="Individual Chicago Landmark: a permit to alter, demolish or add to it needs the Commission on Chicago Landmarks' written approval (§2-120-740).")
    n = next(x for x in _ctx("B3-2", overlays=[lm]).coverage_notes if x["id"] == "landmark")
    assert "Noel State Bank" in n["text"] and "written approval" in n["text"] and "does not assess" in n["text"]
    assert n["section"] == "2-120-740"
    # a historic district the layer does NOT flag as a Chicago Landmark district gets no landmark note
    plain = OverlayDistrict(layer_type="historic_district", name="Some District", detail=None)
    assert "landmark" not in _ids(_ctx(overlays=[plain]))


def test_chrs_orange_or_red_notes_the_90_day_demolition_hold_pinned_to_the_code():
    for color in ("orange", "red"):
        n = next(x for x in _ctx(flags=ParcelFlags(chrs_rating=color)).coverage_notes if x["id"] == "chrs_demolition_delay")
        assert color in n["text"] and "90 days" in n["text"] and n["section"] == "14A-4-407.6"
    assert "chrs_demolition_delay" not in _ids(_ctx(flags=ParcelFlags(chrs_rating="yellow")))
    assert "chrs_demolition_delay" not in _ids(_ctx())
    t = _text("14A-4-407")
    assert "color coded orange or red in the Chicago Historic Resources Survey" in t and "not to exceed 90 days" in t


def test_a_landmark_replaces_the_chrs_note_since_the_code_exempts_designated_landmarks():
    lm = OverlayDistrict(layer_type="landmark_building", name="X", detail="Individual Chicago Landmark: ... (§2-120-740).")
    ids = _ids(_ctx(overlays=[lm], flags=ParcelFlags(chrs_rating="orange")))
    assert "landmark" in ids and "chrs_demolition_delay" not in ids
    assert "Exceptions: 1. Chicago Landmarks , subject to Section 14A-4-407.7" in _text("14A-4-407")


def test_a_recent_rezoning_is_a_parcel_note_with_the_clerk_link():
    import datetime
    recent = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    n = next(x for x in _ctx(ordinance_date=recent, ordinance_num="O2026-1", clerk_url="https://clerk/x").coverage_notes if x["id"] == "recently_rezoned")
    assert recent in n["text"] and "up to 90 days" in n["text"] and n["link"] == "https://clerk/x"
    assert "recently_rezoned" not in _ids(_ctx(ordinance_date="2007-09-05"))


def test_adu_limits_note_only_when_the_zone_has_limits():
    z10 = OverlayDistrict(layer_type="adu_area", name="ADU-Allowed RS Area — Zone 10",
                          detail="Limitations: Annual Limits, Owner Occupancy Limits (§17-7-0573, §17-7-0574).")
    n = next(x for x in _ctx("RS-3", overlays=[z10]).coverage_notes if x["id"] == "adu_limits")
    assert "Annual Limits, Owner Occupancy Limits" in n["text"]
    assert "adu_limits" not in _ids(_ctx("RT-4", overlays=[z10]))  # RT: by right, no zone limits
    assert "adu_limits" not in _ids(_ctx("RS-2"))


def test_parcel_notes_come_before_general_ones_and_everything_is_json_safe():
    pd = OverlayDistrict(layer_type="planned_development", name="Planned Development 835", link="https://x/PD835.pdf")
    ids = _ids(_ctx("PD 835", overlays=[pd]))
    assert ids.index("planned_development") < ids.index("aldermanic")
    json.dumps(_ctx("PD 835", overlays=[pd]).model_dump(exclude_none=True)["coverage_notes"])


def test_prompt_rule_asks_the_answer_to_restate_the_notes_that_apply():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("36. WHAT THE PAGE DOES NOT COVER")
    rule = SYNTHESIZER_SYSTEM[i : i + 2000]
    assert "coverage_notes" in rule and "official_letter" in rule and "screening" in rule.lower()


def test_build_is_total_on_missing_inputs():
    assert [n["id"] for n in build_coverage_notes(zoning=None, regulatory=None, property_=None, neighborhood=None, adu=None, code_vintage=None)] == ["aldermanic", "map_lag", "official_letter"]
