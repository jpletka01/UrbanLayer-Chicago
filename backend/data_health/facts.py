"""The fact snapshot: what an answer or a report said about a parcel, kept small (WS6 M8, plan §4.3).

A conversation message and a rendered report each keep a snapshot of the facts they rested on, so that a
later reader can be told what changed since ("Answered Oct 2; since then the map shows B2-3, not B3-2").
This module only *builds* the snapshot. Comparing one with today's facts is M9.

**Built on the server, from a validated ``ContextObject``.** A saved message's snapshot is computed when the
message is stored, from the context the server parsed; a ``facts`` field in the client's payload is never
read. (A user can still edit their own message's context; that only changes the notes on their own
conversation, and never reaches another reader.)

What goes in is what a material change is measured against (§4.4): the district and its ordinance, the
overlays (sorted, names normalized), the flags that drive a verdict, the standards, the code text's
vintage and the sections the answer cited, the parcel's headline records, the date each source was
current, and what could not be checked. Crime, 311, permits, comps and the like are not here: they move
daily and are never "material".

Pure: no request, no model. ``SNAPSHOT_VERSION`` is stored in every snapshot.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

SNAPSHOT_VERSION = 1

# The overlay flags a verdict or a use depends on (RegulatorySummary booleans).
FLAG_KEYS = (
    "in_planned_development", "in_landmark_district", "is_landmark_building", "in_historic_district",
    "on_national_register", "in_lakefront_protection", "on_pedestrian_street", "in_special_district", "in_pmd",
    "in_tod_area", "in_adu_area", "in_aro_zone", "in_ssa",
)
_BULK_FACTS = ("zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit")


def normalize_name(name: str | None) -> str:
    """An overlay's name as a comparison key: case, spacing and punctuation never make a "change"."""
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (name or "").lower())).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_assessment_year(prop: Any) -> int | None:
    years = [r.year for r in (getattr(prop, "assessment_history", None) or []) if getattr(r, "year", None)]
    return max(years) if years else None


def snapshot(
    context: Any, *, provenance: dict[str, dict] | None = None, zone_definition: dict | None = None,
    answered_at: str | None = None, lat: float | None = None, lon: float | None = None,
    address: str | None = None, pin: str | None = None, unchecked: list[str] | None = None,
) -> dict:
    """The snapshot of ``context`` (a ``ContextObject``) as a JSON-safe dict, about 2 to 4 KB."""
    from backend.data_health.failures import failed_keys
    from backend.legislation.currency import parcel_cited_sections

    prov = provenance if provenance is not None else (getattr(context, "provenance", None) or {})
    zoning = getattr(context, "parcel_zoning", None)
    reg = getattr(context, "regulatory", None)
    prop = getattr(context, "property", None)
    zd = zone_definition if zone_definition is not None else (getattr(context, "zone_definition", None) or {})
    overlays = list(getattr(reg, "overlays", None) or [])
    notes = getattr(context, "coverage_notes", None) or []
    zone_class = getattr(zoning, "zone_class", None)

    code_vintage = getattr(context, "code_vintage", None) or {}
    bulk = list(dict.fromkeys(prov[f]["section"] for f in _BULK_FACTS if f in prov and prov[f].get("section")))
    cited = parcel_cited_sections(zone_class, overlays, note_sections=[n.get("section") for n in notes if isinstance(n, dict)]) if zone_class else []

    sources: dict[str, dict] = {}
    for e in prov.values():
        sid = e.get("source_id")
        if sid and sid not in sources:
            sources[sid] = {k: e[k] for k in ("as_of", "period") if e.get(k)}

    out: dict[str, Any] = {
        "v": SNAPSHOT_VERSION,
        "answered_at": answered_at or _now_iso(),
        "pin": pin or getattr(context, "parcel_pin", None) or getattr(prop, "pin14", None),
        "lat": lat, "lon": lon,
        "address": address or getattr(context, "resolved_address", None),
        "zoning": ({
            "zone_class": zone_class, "ordinance_num": zoning.ordinance_num, "ordinance_date": zoning.ordinance_date,
            "map_updated": zoning.map_updated,
        } if zoning is not None else None),
        "overlays": sorted([o.layer_type, normalize_name(o.name)] for o in overlays),
        "flags": ({k: bool(getattr(reg, k, False)) for k in FLAG_KEYS} if reg is not None else None),
        "unchecked_overlays": sorted(getattr(reg, "unchecked_overlays", None) or []) if reg is not None else [],
        "standards": ({
            "far": zd.get("far"), "max_height": zd.get("max_height"), "min_lot_area_per_unit": zd.get("min_lot_area_per_unit"),
            "unit_yield": (getattr(context, "unit_yield", None) or {}).get("units"),
        } if zd else None),
        "code": {"current_through": code_vintage.get("current_through"), "cited_sections": cited, "bulk_sections": bulk},
        "property": ({
            "land_sqft": prop.land_sqft, "bldg_sqft": prop.bldg_sqft, "assessment_year": _latest_assessment_year(prop),
            "assessed_total": prop.total_assessed_value, "tax_year": prop.tax_year, "est_tax": prop.estimated_annual_tax,
        } if prop is not None else None),
        "passed": {
            "rezonings": [h["record"] for h in (getattr(context, "passed_not_on_map", None) or [])],
            "landmark_designations": [h["record"] for h in (getattr(context, "passed_landmark_designations", None) or [])],
        },
        "sources": sources,
        "unchecked": sorted(set(failed_keys(unchecked if unchecked is not None else getattr(context, "partial_failures", None)))),
    }
    return out


def resolved_parcel(snap: dict | None) -> bool:
    """True when the snapshot is of a parcel (a district or a property was resolved). An answer about the
    neighborhood or the code has nothing to compare, so it gets no snapshot stored."""
    return bool(snap and (snap.get("zoning") or snap.get("property")))
