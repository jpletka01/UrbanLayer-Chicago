"""V1: every Profile fact a reader could act on carries a dated source.

The code sections are pinned to the ingested Municipal Code's own headings, so a
citation can't point at the wrong section; the endpoint test checks the payload."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend import main
from backend.models import ContextObject, OverlayDistrict, PropertySummary, RegulatorySummary, ZoningSummary
from backend.provenance import BULK_SECTIONS, bulk_family, build_provenance, entry_is_dated
from backend.retrieval.zoning_definitions import get_zone_definition

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"
FAMILY_FILE = {"R": "17-2-0300", "BC": "17-3-0400", "M": "17-5-0400", "D": "17-4-0400"}


def _body(section_file: str) -> str:
    path = SECTIONS / f"{section_file}.json"
    if not path.exists():
        pytest.skip("ordinance corpus not present")
    return " ".join(json.loads(path.read_text())["body_paragraphs"])


def _ctx(zone="RM-4.5", **zkw) -> ContextObject:
    return ContextObject(
        parcel_zoning=ZoningSummary(zone_class=zone, ordinance_num="A7210", ordinance_date="2007-09-05", map_updated="2021-10-27", **zkw),
        regulatory=RegulatorySummary(overlays=[
            OverlayDistrict(layer_type="special_district", name="Predominance of the Block (606) District", link="https://codelibrary.amlegal.com/x"),
            OverlayDistrict(layer_type="aro_zone", name="Affordable Requirements Ordinance Zones"),
        ]),
        property=PropertySummary(pin14="16012280180000", land_sqft=3191, land_sqft_source="geometry"),
    )


def _build(ctx, zone="RM-4.5", pin="16012280180000", conf="authoritative"):
    return build_provenance(context=ctx, zone_definition=get_zone_definition(zone).__dict__, resolved_pin=pin, resolved_confidence=conf, query_date="2026-10-02")


# --- citations are pinned to the code's own headings -----------------------------------------------

def test_bulk_sections_exist_in_the_ingested_code_with_the_right_headings():
    headings = {
        "17-2-0304-A": "Standards", "17-2-0311-A": "Standards", "17-2-0303-A": "Minimum Lot Area per Unit Standards",
        "17-3-0403-A": "Standards", "17-3-0408-A": "Standards", "17-3-0402-A": "Standards",
        "17-5-0404": "Floor Area Ratio", "17-4-0405-A": "Standards", "17-4-0407": "Maximum Building Height",
        "17-4-0404-A": "Standards",
    }
    for fam, facts in BULK_SECTIONS.items():
        text = _body(FAMILY_FILE[fam])
        for fact, sec in facts.items():
            if sec is None:
                continue
            assert f"{sec} {headings[sec]}" in text, (fam, fact, sec)
    # the family titles say what the facts are
    assert "17-2-0304 Floor Area Ratio" in _body("17-2-0300") and "17-2-0311 Building Height" in _body("17-2-0300")
    assert "17-3-0402 Lot area per unit" in _body("17-3-0400")


def test_families():
    assert [bulk_family(z) for z in ("RS-3", "RT-4", "RM-4.5", "B1-2", "C3-5", "M1-2", "DX-7", "DS-3")] == ["R", "R", "R", "BC", "BC", "M", "D", "D"]
    assert all(bulk_family(z) is None for z in ("PD 835", "POS-1", "", None, "ZZ-9"))


# --- the entries -------------------------------------------------------------------------------------

def test_district_entry_carries_the_ordinance_and_both_dates():
    e = _build(_ctx())["zoning.district"]
    assert (e["record_id"], e["effective_date"], e["as_of"], e["query_date"]) == ("A7210", "2007-09-05", "2021-10-27", "2026-10-02")
    assert e["kind"] == "official_record" and "layer 1" in e["source"]


def test_a_recent_rezoning_links_the_clerk_record():
    z = ContextObject(parcel_zoning=ZoningSummary(zone_class="RT-4", ordinance_num="O2026-0025358", application_num="23082T1",
                                                  ordinance_date="2026-06-16", map_updated="2026-08-21",
                                                  clerk_url="https://chicityclerkelms.chicago.gov/Matter/?matterId=abc"))
    e = build_provenance(context=z, zone_definition=get_zone_definition("RT-4").__dict__, resolved_pin=None, resolved_confidence=None, query_date="2026-10-02")["zoning.district"]
    assert e["url"].startswith("https://chicityclerkelms.chicago.gov/") and e["record_id"] == "O2026-0025358"
    assert "23082T1" in e["note"]


def test_standards_cite_their_code_sections_and_the_codes_vintage():
    p = _build(_ctx())
    assert [p[f"zoning.{f}"]["section"] for f in ("far", "max_height", "min_lot_area_per_unit")] == ["17-2-0304-A", "17-2-0311-A", "17-2-0303-A"]
    assert all(p[f"zoning.{f}"]["as_of"] == "2026-03-18" and p[f"zoning.{f}"]["kind"] == "code_text" for f in ("far", "max_height", "min_lot_area_per_unit"))
    bc = _build(_ctx("B1-2"), zone="B1-2")
    assert bc["zoning.far"]["section"] == "17-3-0403-A" and bc["zoning.min_lot_area_per_unit"]["section"] == "17-3-0402-A"


def test_no_standard_without_a_code_section_or_a_value():
    m = _build(_ctx("M1-2"), zone="M1-2")  # M districts: a FAR, but no height or per-unit standard
    assert "zoning.far" in m and "zoning.max_height" not in m and "zoning.min_lot_area_per_unit" not in m
    pd = _build(_ctx("PD 835"), zone="PD 835")  # PD: standards live in the ordinance, never cited from Title 17
    assert not any(k.startswith("zoning.") and k != "zoning.district" for k in pd)
    assert "zoning.district" in pd


def test_overlays_each_get_an_entry_with_their_layer_and_link():
    p = _build(_ctx())
    sd = p["overlay.special_district"]
    assert "Special Districts" in sd["source"] and "layer 9" in sd["source"] and sd["url"].startswith("https://codelibrary")
    assert sd["record_id"] == "Predominance of the Block (606) District"
    assert "layer 20" in p["overlay.aro_zone"]["source"]


def test_identity_is_authoritative_or_marked_approximate():
    ok = _build(_ctx())["parcel.identity"]
    assert ok["kind"] == "official_record" and ok["url"].endswith("/pin/16012280180000")
    approx = _build(_ctx(), conf="approximate")["parcel.identity"]
    assert approx["kind"] == "derived" and "not confirmed" in approx["note"].lower()
    assert "parcel.identity" not in _build(_ctx(), pin=None)


def test_area_entries_name_their_dataset():
    p = _build(_ctx())
    assert "property-tax database" in p["property.land_sqft"]["source"]
    assert "property.bldg_sqft" not in p  # no building area, no entry


def test_every_entry_is_dated_and_json_safe():
    p = _build(_ctx())
    assert p and all(entry_is_dated(e) for e in p.values())
    assert all(e["query_date"] == "2026-10-02" for e in p.values())
    json.dumps(p)
    assert p["code.vintage"]["as_of"] == "2026-03-18"


def test_entry_is_dated_rejects_missing_or_malformed():
    assert not entry_is_dated(None) and not entry_is_dated({}) and not entry_is_dated({"as_of": "yesterday"})
    assert entry_is_dated({"effective_date": "2007-09-05"})


# --- the /api/scorecard payload ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scorecard_payload_carries_provenance_for_district_standards_and_overlays():
    rl = main.ResolvedLocation(41.9047, -87.6887, "1256 N Artesian Ave", "16012280180000", "authoritative")
    data = {"context": _ctx(), "comparables": None}
    with patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)), \
         patch.object(main, "_fetch_scorecard_data", new=AsyncMock(return_value=data)):
        out = await main.scorecard(address="1256 N Artesian Ave")
    prov = out["provenance"]
    for key in ("zoning.district", "zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit", "overlay.special_district", "parcel.identity", "code.vintage"):
        assert key in prov and entry_is_dated(prov[key]), key
