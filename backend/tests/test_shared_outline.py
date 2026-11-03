"""A parcel outline shared by a whole divided development is no lot's area (decision Items 46, 59)."""

from backend.models import ContextObject, PropertySummary
from backend.provenance import build_provenance, confidence_state


def _prov(**prop) -> dict:
    ctx = ContextObject(property=PropertySummary(pin14="14-28-319-102-0000", **prop))
    return build_provenance(context=ctx, zone_definition=None, resolved_pin="14-28-319-102-0000",
                            resolved_confidence="authoritative", query_date="2026-11-03")


def test_shared_outline_withholds_the_lot_area_with_its_reason():
    prov = _prov(land_sqft=None, shared_outline_with=29)
    entry = prov["property.land_sqft"]
    assert entry["confidence"] == "withheld"
    assert "shared_outline" in entry["confidence_reasons"]
    assert entry["shared_outline_with"] == 29
    assert entry.get("value") is None


def test_an_assessor_lot_area_stands_even_with_a_shared_outline():
    prov = _prov(land_sqft=2100, land_sqft_source="assessor", shared_outline_with=29)
    assert prov["property.land_sqft"]["confidence"] != "withheld"


def test_confidence_state_reads_the_shared_outline_field():
    state, reasons = confidence_state({"shared_outline_with": 3})
    assert state == "withheld" and reasons == ["shared_outline"]
