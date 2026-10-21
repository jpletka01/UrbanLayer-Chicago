"""V1: every Profile fact a reader could act on carries a dated source.

The code sections are pinned to the ingested Municipal Code's own headings, so a
citation can't point at the wrong section; the endpoint test checks the payload."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from backend import main
from backend.data_health.registry import BY_ID
from backend.models import ContextObject, OverlayDistrict, PropertySummary, RegulatorySummary, ZoningSummary
from backend.provenance import (
    BULK_SECTIONS, FACTS, METHOD_TEXT, ProvenanceEntry, bulk_family, build_provenance, entry_is_dated,
    make_entry, resolve_as_of, weakest_tier,
)
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
    assert all(p[f"zoning.{f}"]["as_of"] == "2026-06-17" and p[f"zoning.{f}"]["kind"] == "code_text" for f in ("far", "max_height", "min_lot_area_per_unit"))
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
    assert p["code.vintage"]["as_of"] == "2026-06-17"


def test_entry_is_dated_rejects_missing_or_malformed():
    assert not entry_is_dated(None) and not entry_is_dated({}) and not entry_is_dated({"as_of": "yesterday"})
    assert entry_is_dated({"effective_date": "2007-09-05"})


# --- the /api/scorecard payload ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scorecard_payload_carries_provenance_for_district_standards_and_overlays():
    rl = main.ResolvedLocation(41.9047, -87.6887, "1256 N Artesian Ave", "16012280180000", "authoritative")
    data = {"context": _ctx(), "comparables": None}
    with patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)), \
         patch.object(main, "_fetch_scorecard_data", new=AsyncMock(return_value=data)), \
         patch("backend.retrieval.property.address_points.address_point_pins", new=AsyncMock(return_value=[])), \
         patch("backend.retrieval.property.parcel_addresses.assessor_address_pins", new=AsyncMock(return_value=[])):
        out = await main.scorecard(address="1256 N Artesian Ave")
    prov = out["provenance"]
    for key in ("zoning.district", "zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit", "overlay.special_district", "parcel.identity", "code.vintage"):
        assert key in prov and entry_is_dated(prov[key]), key


# --- schema v2 (WS0 M2) -------------------------------------------------------------------------------


def _everything() -> dict:
    """An entry of every kind the Profile emits, including both identity and area variants."""
    ctx = _ctx()
    ctx.property.bldg_sqft, ctx.property.bldg_sqft_source = 1900, "footprint"
    out = _build(ctx)
    out["identity.approx"] = _build(ctx, conf="approximate")["parcel.identity"]
    return out


def test_every_entry_validates_against_the_schema_and_is_json_safe():
    for key, e in _everything().items():
        ProvenanceEntry.model_validate(e)
        assert set(e) >= {"label", "kind", "source", "record_id", "url", "section", "as_of", "effective_date", "query_date"}, key
        assert e["tier"] and e["method_key"] and e["method"] and e["as_of_basis"] and e["confidence"] == "standard", key
    json.dumps(_everything())


def test_the_schema_rejects_unknown_fields_and_values():
    good = _build(_ctx())["zoning.district"]
    with pytest.raises(ValidationError):
        ProvenanceEntry.model_validate({**good, "surprise": 1})
    with pytest.raises(ValidationError):
        ProvenanceEntry.model_validate({**good, "tier": "gold_standard"})
    with pytest.raises(ValidationError):
        ProvenanceEntry.model_validate({**good, "method_key": "vibes"})
    with pytest.raises(KeyError):
        make_entry("not.a.fact", query_date="2026-10-02")


def test_kind_is_an_alias_of_tier():
    for key, e in _everything().items():
        expected = {"official_record": "official_record", "official_publication": "code_text"}.get(e["tier"], "derived")
        assert e["kind"] == expected, key
    p = _build(_ctx())
    assert p["zoning.far"]["tier"] == "official_publication" and p["code.vintage"]["tier"] == "official_publication"
    assert p["zoning.district"]["tier"] == "official_record"


def test_v1_fields_are_unchanged_by_v2():
    """The wire contract the Zoning card, the sources footer and the citation check read."""
    p = _build(_ctx())
    d = p["zoning.district"]
    assert (d["label"], d["record_id"], d["as_of"], d["effective_date"]) == (
        "Zoning district RM-4.5", "A7210", "2021-10-27", "2007-09-05")
    assert d["url"].startswith("https://gisapps.chicago.gov/")
    assert p["zoning.far"]["record_id"] == "§17-2-0304-A" and p["zoning.far"]["as_of"] == "2026-06-17"
    assert p["overlay.special_district"]["as_of"] is None  # the layer has no edit date; never invented
    assert p["parcel.identity"]["record_id"] == "16012280180000"


def test_dates_carry_their_meaning():
    p = _build(_ctx())
    assert p["zoning.district"]["as_of_basis"] == "record_updated" and p["zoning.district"]["age_days"] > 700
    assert "old_source" not in p["zoning.district"]["confidence_reasons"]  # a record's edit date is not the dataset's age
    assert p["zoning.far"]["as_of_basis"] == "current_through" and p["code.vintage"]["as_of_basis"] == "current_through"
    ov = p["overlay.special_district"]
    assert ov["as_of_basis"] == "queried" and "age_days" not in ov


def test_values_are_the_figures_as_displayed():
    p = _build(_ctx())
    assert p["zoning.district"]["value"] == "RM-4.5" and p["property.land_sqft"]["value"] == 3191
    assert p["zoning.far"]["value"] == get_zone_definition("RM-4.5").far
    assert p["parcel.identity"]["value"] == "16012280180000" and p["code.vintage"]["value"] == p["code.vintage"]["as_of"]


def test_a_polygon_area_is_our_calculation_on_the_countys_geometry():
    land = _build(_ctx())["property.land_sqft"]  # land_sqft_source == "geometry"
    assert land["tier"] == "our_calculation" and land["kind"] == "derived" and land["method_key"] == "calculation"
    assert land["inputs"] == ["cook.ptaxsim"] and land["basis_tier"] == BY_ID["cook.ptaxsim"].tier == "official_estimate"
    assert land["source_id"] == "cook.ptaxsim"


def test_a_stated_area_is_a_recorded_figure_on_its_source():
    ctx = _ctx()
    ctx.property.land_sqft_source = "assessor"
    ctx.property.bldg_sqft, ctx.property.bldg_sqft_source = 1900, "footprint"
    p = _build(ctx)
    assert (p["property.land_sqft"]["tier"], p["property.land_sqft"]["source_id"]) == ("official_record", "cook.assessor.characteristics")
    assert (p["property.bldg_sqft"]["method_key"], p["property.bldg_sqft"]["source_id"]) == ("recorded", "chi.building_footprints")
    assert "inputs" not in p["property.bldg_sqft"]


def test_approximate_identity_is_a_calculation_on_the_parcel_universe():
    e = _build(_ctx(), conf="approximate")["parcel.identity"]
    assert e["tier"] == "our_calculation" and e["inputs"] == ["cook.parcel_universe"] and e["basis_tier"] == "official_record"
    ok = _build(_ctx())["parcel.identity"]
    assert ok["tier"] == "official_record" and ok["method_key"] == "recorded" and "inputs" not in ok


def test_an_unknown_area_dataset_is_still_a_recorded_county_figure():
    ctx = _ctx()
    ctx.property.land_sqft_source = "something_new"
    e = _build(ctx)["property.land_sqft"]
    assert e["source"] == "something_new" and e["tier"] == "official_record" and e["source_id"] == "cook.assessor.characteristics"


# --- the registry agrees with the facts ----------------------------------------------------------------------

def _lists(fact_id: str, keys) -> bool:
    """A registry key covers its own fact and the facts under it (``area.tract`` lists ``area.tract.median_gross_rent``)."""
    return fact_id in keys or any(fact_id.startswith(k + ".") for k in keys)


def test_every_fact_names_a_registered_source_that_lists_it():
    for fact_id, spec in FACTS.items():
        for sid in (spec.source_id, *spec.alt_source_ids, *spec.input_source_ids):
            assert sid in BY_ID, (fact_id, sid)
            assert _lists(fact_id, BY_ID[sid].fact_keys), (fact_id, sid)


def test_a_recorded_figures_tier_equals_its_sources_registry_tier():
    for fact_id, spec in FACTS.items():
        if spec.method_key in ("recorded", "published_text", "code_table"):
            for sid in (spec.source_id, *spec.alt_source_ids):
                assert BY_ID[sid].tier == spec.tier, (fact_id, sid, BY_ID[sid].tier, spec.tier)


def test_every_emitted_entry_resolves_to_a_registered_source():
    for key, e in _everything().items():
        assert e["source_id"] in BY_ID, (key, e["source_id"])
        if e["method_key"] in ("recorded", "published_text", "code_table"):
            assert e["tier"] == BY_ID[e["source_id"]].tier, key


def test_every_overlay_layer_has_a_fact_and_every_fact_key_in_the_registry_that_we_emit_resolves():
    from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS

    assert {f"overlay.{m['type']}" for m in OVERLAY_LAYERS.values()} <= set(FACTS)
    for sid, spec in BY_ID.items():
        for fk in spec.fact_keys:
            for fid in [f for f in FACTS if f == fk or f.startswith(fk + ".")]:
                # the registry's claim about a fact we model must be the fact's own source
                spec_f = FACTS[fid]
                assert sid in (spec_f.source_id, *spec_f.alt_source_ids, *spec_f.input_source_ids), (fid, sid)


def test_every_method_key_has_english_text():
    from typing import get_args

    from backend.provenance import MethodKey

    assert set(get_args(MethodKey)) == set(METHOD_TEXT)


# --- calculations are never stronger than their weakest input ------------------------------------------------

def test_a_calculation_takes_its_weakest_inputs_tier():
    assert weakest_tier(["official_record", "official_estimate"]) == "official_estimate"
    assert weakest_tier(["official_publication", "official_record"]) == "official_publication"
    assert weakest_tier(["official_record", "ai_extracted", "official_estimate"]) == "ai_extracted"
    assert weakest_tier([]) is None
    e = make_entry("zoning.far", query_date="2026-10-02", tier="our_calculation", method_key="calculation",
                   inputs=["zoning.far", "cook.ptaxsim", "artifact.zoning_cache"])
    assert e["basis_tier"] == "ai_extracted"  # D on E: the buildable footprint case


# --- the as-of precedence --------------------------------------------------------------------------------------

def test_as_of_precedence():
    assert resolve_as_of("chi.zoning.districts", response_date="2026-08-21", response_basis="record_updated") == ("2026-08-21", "record_updated")
    assert resolve_as_of("chi.building_footprints") == ("2015-08-15", "vintage")  # a frozen source states its vintage
    assert resolve_as_of("chi.crime") == (None, "queried")  # live and no date: we only know when we asked
    assert resolve_as_of(None) == (None, "queried") and resolve_as_of("no.such.source") == (None, "queried")


def test_as_of_prefers_data_healths_latest_check_over_the_frozen_vintage(monkeypatch):
    import sys
    import types

    mod = types.ModuleType("backend.data_health.status")
    mod.latest = lambda sid: {"content_through": "2026-10-19T00:00:00", "published_at": "2026-10-01"}
    monkeypatch.setitem(sys.modules, "backend.data_health.status", mod)
    monkeypatch.setattr("backend.data_health.status", mod, raising=False)
    assert resolve_as_of("chi.crime") == ("2026-10-19", "period_end")  # the newest date in the data
    mod.latest = lambda sid: {"published_at": "2026-10-01"}
    assert resolve_as_of("chi.crime") == ("2026-10-01", "source_updated")
    mod.latest = lambda sid: 1 / 0  # an unreadable store falls through, never raises
    assert resolve_as_of("chi.building_footprints") == ("2015-08-15", "vintage")
