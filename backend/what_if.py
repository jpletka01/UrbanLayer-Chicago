"""What if this parcel were in another district? Table arithmetic for the Property Profile (WS5 PR2).

Pure: the district table (``zoning_definitions``, ordinance-parity tested) and the lot area the Profile already
resolved.  No fetch, no model.  For the parcel's current district and one chosen district: FAR, the floor area
that FAR allows on this lot, the height, and the units the lot area allows.  It cannot know parking, setbacks
for this lot's shape, or whether City Council would approve a change; the Profile says so.

Wording rule for every caller: "the district's table allows", never "you can build".
"""

from __future__ import annotations

import re

from backend.retrieval.zoning_definitions import ZONE_CLASS_DATA, get_zone_definition, max_units_by_lot_area

# The residential districts in order of intensity (Title 17, Article 2).
RESIDENTIAL_LADDER = ("RS-1", "RS-2", "RS-3", "RT-3.5", "RT-4", "RM-4.5", "RM-5", "RM-5.5", "RM-6", "RM-6.5")
# Districts the comparison never offers: planned developments are set by their own ordinance, and parks/open
# space carry no development standards in the table.
_EXCLUDED_PREFIXES = ("PD", "PMD", "POS")

_DASH = re.compile(r"^([A-Z]+\d?)-(\d+(?:\.\d+)?)$")


class WhatIfError(ValueError):
    """The district cannot be compared (not in the table, or a planned development)."""


def comparable_districts() -> list[str]:
    """Every district the table can compare, in table order."""
    return sorted(z for z in ZONE_CLASS_DATA if not z.startswith(_EXCLUDED_PREFIXES))


def _dash_order(zone: str) -> tuple[str, float] | None:
    m = _DASH.match(zone)
    return (m.group(1), float(m.group(2))) if m else None


def suggestions(current: str | None, limit: int = 3) -> list[str]:
    """A short list of the plausible next districts up from ``current`` (the choice list a non-technical user
    starts from; "any district" covers the rest).  Empty for a planned development or an unknown class."""
    zone = (current or "").strip().upper()
    if not zone or zone.startswith(_EXCLUDED_PREFIXES) or zone not in ZONE_CLASS_DATA:
        return []
    if zone in RESIDENTIAL_LADDER:
        i = RESIDENTIAL_LADDER.index(zone)
        return list(RESIDENTIAL_LADDER[i + 1:i + 1 + limit])
    parsed = _dash_order(zone)
    if parsed is None:
        return []
    family, dash = parsed
    out: list[str] = []
    # B1/B2 commonly step to the broader B3 at the same intensity.
    if family in ("B1", "B2"):
        same = f"B3-{parsed[1]:g}"
        if same in ZONE_CLASS_DATA:
            out.append(same)
    higher = sorted((d for d in ZONE_CLASS_DATA if (p := _dash_order(d)) and p[0] == family and p[1] > dash),
                    key=lambda d: _dash_order(d)[1])  # type: ignore[index]
    out.extend(higher)
    return out[:limit]


def district_figures(zone_class: str, lot_sqft: float | None, *, in_606: bool | None = None) -> dict:
    """The table's figures for one district on this lot.  Raises ``WhatIfError`` for a district the table cannot
    compare."""
    zone = (zone_class or "").strip().upper()
    if zone.startswith(_EXCLUDED_PREFIXES):
        raise WhatIfError(f"{zone}: a planned development's limits come from its own ordinance, not the district table")
    if zone not in ZONE_CLASS_DATA:
        raise WhatIfError(f"{zone}: not a district in the zoning table")
    d = get_zone_definition(zone)
    lot = int(round(lot_sqft)) if lot_sqft and lot_sqft > 0 else None
    uy = max_units_by_lot_area(zone, lot, in_606=in_606) if lot else None
    return {
        "zone_class": zone,
        "name": d.name,
        "code_section": d.code_section,
        "far": d.far,
        "max_floor_area_sqft": round(lot * d.far) if lot and d.far else None,
        "max_height": d.max_height,
        "min_lot_area_per_unit": d.min_lot_area_per_unit,
        "units_by_lot_area": uy["units"] if uy else None,
        "units_arithmetic": uy["arithmetic"] if uy else None,
    }


def compare(current: str, target: str, lot_sqft: float | None, *, in_606: bool | None = None) -> dict:
    """The parcel's district beside the chosen one, plus the choice list.  ``in_606`` only matters for RS-3."""
    target_figures = district_figures(target, lot_sqft, in_606=in_606)
    try:
        current_figures: dict | None = district_figures(current, lot_sqft, in_606=in_606)
    except WhatIfError:
        current_figures = None  # a PD parcel can still look at a district; its own column says why it is blank
    return {
        "lot_sqft": int(round(lot_sqft)) if lot_sqft and lot_sqft > 0 else None,
        "current": current_figures,
        "target": target_figures,
        "suggestions": suggestions(current),
    }
