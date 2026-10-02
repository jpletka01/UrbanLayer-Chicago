"""Where each Property Profile fact came from, and how current that is.

A fact a reader could act on carries a dated source: the official record it was read
from (layer, ordinance, feature), or the code section it is computed from, with the
date the source says it is current and the date we queried it. This is the data
behind "click a number, see the source" (V2); it makes a claim checkable instead of
asking to be trusted.

Every entry is a plain dict (JSON-safe), keyed by a stable fact id:

    zoning.district                    the district + the ordinance that set it
    zoning.far / .max_height /
      .min_lot_area_per_unit           the standard + the code section it comes from
    overlay.<layer_type>               each overlay found + the layer it came from
    parcel.identity                    which parcel, and how it was identified
    property.land_sqft / .bldg_sqft    the area figure + which dataset supplied it
    code.vintage                       how current the indexed Municipal Code is

Fields: ``label`` (plain words), ``kind`` (official_record | code_text | derived),
``source`` (the dataset or code), ``record_id``, ``url``, ``section`` (a code section
id the source viewer can open), ``as_of`` (when the source says its record last
changed / the code is current through), ``effective_date`` (when the rule took
effect, e.g. the ordinance date) and ``query_date`` (when we asked). Any may be None;
an entry always carries a ``query_date``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.code_vintage import get_code_vintage
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS
from backend.retrieval.zoning_definitions import _parse_zone_prefix

ZONING_LAYER = "City of Chicago Zoning Districts, Zoning MapServer layer 1"
CODE_SOURCE = "Municipal Code of Chicago, Title 17 (Zoning Ordinance)"

# Code sections each standard comes from, by district family. Pinned to the ingested
# code's section headings in tests/test_provenance.py. None = the code sets no such
# standard for the family (M districts have no height or per-unit standard).
BULK_SECTIONS: dict[str, dict[str, str | None]] = {
    "R": {"far": "17-2-0304-A", "max_height": "17-2-0311-A", "min_lot_area_per_unit": "17-2-0303-A"},
    "BC": {"far": "17-3-0403-A", "max_height": "17-3-0408-A", "min_lot_area_per_unit": "17-3-0402-A"},
    "M": {"far": "17-5-0404", "max_height": None, "min_lot_area_per_unit": None},
    "D": {"far": "17-4-0405-A", "max_height": "17-4-0407", "min_lot_area_per_unit": "17-4-0404-A"},
}

_BULK_LABELS = {
    "far": "Floor area ratio",
    "max_height": "Maximum building height",
    "min_lot_area_per_unit": "Minimum lot area per dwelling unit",
}

_LAYER_ID_BY_TYPE = {meta["type"]: lid for lid, meta in OVERLAY_LAYERS.items()}

_AREA_SOURCES = {
    "assessor": "Cook County Assessor (parcel characteristics)",
    "gis": "Cook County GIS parcel layer",
    "geometry": "Parcel polygon area (Cook County property-tax database)",
    "condo_unit": "Cook County Assessor condominium characteristics (one unit's area)",
    "commercial_valuation": "Cook County Assessor commercial valuation (economic-unit total)",
    "footprint": "City of Chicago building footprints (ground-floor area)",
    "energy_benchmark": "City of Chicago energy benchmarking (owner-reported gross floor area)",
}


def bulk_family(zone_class: str | None) -> str | None:
    """'R', 'BC', 'M', 'D' for the districts that have bulk tables; None for PD/POS/unknown."""
    if not zone_class:
        return None
    prefix, _ = _parse_zone_prefix(zone_class.strip().upper())
    if prefix in ("RS", "RT", "RM"):
        return "R"
    if prefix in ("B1", "B2", "B3", "C1", "C2", "C3"):
        return "BC"
    if prefix in ("M1", "M2", "M3"):
        return "M"
    if prefix in ("DX", "DC", "DR", "DS"):
        return "D"
    return None


def _entry(label: str, kind: str, query_date: str, **fields) -> dict:
    base = {
        "label": label, "kind": kind, "source": None, "record_id": None, "url": None,
        "section": None, "as_of": None, "effective_date": None, "query_date": query_date,
    }
    base.update(fields)
    return base


def build_provenance(
    *,
    context,
    zone_definition: dict | None,
    resolved_pin: str | None,
    resolved_confidence: str | None,
    query_date: str | None = None,
) -> dict[str, dict]:
    """Provenance for the facts the Profile shows. ``context`` is the assembled
    ContextObject; a fact that isn't present gets no entry (never a made-up one)."""
    qd = query_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out: dict[str, dict] = {}
    vintage = get_code_vintage()
    zoning = getattr(context, "parcel_zoning", None)

    if zoning is not None:
        out["zoning.district"] = _entry(
            f"Zoning district {zoning.zone_class}", "official_record", qd,
            source=ZONING_LAYER,
            record_id=zoning.ordinance_num,
            url=zoning.clerk_url or zoning.zoning_map_url,
            as_of=zoning.map_updated,
            effective_date=zoning.ordinance_date,
            note=(
                f"Application {zoning.application_num}. " if zoning.application_num else ""
            ) + "as_of is when this district's map record was last edited.",
        )

        fam = bulk_family(zoning.zone_class)
        zd = zone_definition or {}
        if fam and not zd.get("is_fallback"):
            for fact, section in BULK_SECTIONS[fam].items():
                if section is None or zd.get(fact) in (None, ""):
                    continue
                out[f"zoning.{fact}"] = _entry(
                    f"{_BULK_LABELS[fact]} for {zoning.zone_class}", "code_text", qd,
                    source=CODE_SOURCE, record_id=f"§{section}", section=section,
                    as_of=(vintage or {}).get("current_through"),
                    note=f"Code text current through {(vintage or {}).get('label')}." if vintage else None,
                )

    regulatory = getattr(context, "regulatory", None)
    for ov in (regulatory.overlays if regulatory else []):
        lid = _LAYER_ID_BY_TYPE.get(ov.layer_type)
        layer_name = OVERLAY_LAYERS.get(lid, {}).get("name", ov.layer_type) if lid else ov.layer_type
        out[f"overlay.{ov.layer_type}"] = _entry(
            ov.name or layer_name, "official_record", qd,
            source=f"City of Chicago Zoning MapServer, {layer_name}" + (f" (layer {lid})" if lid else ""),
            record_id=ov.ordinance or ov.name,
            url=ov.link,
        )

    if resolved_pin:
        method = (
            "Cook County Address Points or Assessor Parcel Addresses"
            if resolved_confidence == "authoritative"
            else "Nearest parcel to the geocoded point (approximate)"
        )
        out["parcel.identity"] = _entry(
            f"Parcel {resolved_pin}", "official_record" if resolved_confidence == "authoritative" else "derived", qd,
            source=method, record_id=resolved_pin,
            url=f"https://www.cookcountyassessor.com/pin/{resolved_pin}",
            note=None if resolved_confidence == "authoritative" else "Identity not confirmed against an address record.",
        )

    prop = getattr(context, "property", None)
    if prop is not None:
        for fact, label, value, src in (
            ("land_sqft", "Lot area", prop.land_sqft, prop.land_sqft_source),
            ("bldg_sqft", "Building area", prop.bldg_sqft, prop.bldg_sqft_source),
        ):
            if value:
                out[f"property.{fact}"] = _entry(
                    label, "official_record", qd,
                    source=_AREA_SOURCES.get(src or "", src or "Cook County records"),
                    record_id=prop.pin14,
                )

    if vintage:
        out["code.vintage"] = _entry(
            "Municipal Code vintage", "code_text", qd,
            source=vintage.get("source") or CODE_SOURCE, as_of=vintage["current_through"],
            note=vintage.get("label"),
        )
    return out


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def entry_is_dated(entry: dict | None) -> bool:
    """True when the entry carries at least one valid date saying how current it is."""
    if not entry:
        return False
    return any(isinstance(entry.get(k), str) and _ISO.match(entry[k]) for k in ("as_of", "effective_date", "query_date"))
