"""How much of the allowed floor area is built: the capacity states (WS8).

Pure rules, no I/O.  One owner for the census (``eval/capacity_coverage.py``, decision Item 36) and the
Profile's capacity map (Item 39), so the numbers the audit measured and the map the product draws cannot drift.

Two levels:

* ``classify`` and ``polygon_state`` are the Phase 0 census rules, unchanged: a parcel's state from its
  Discovery-index attributes, and a PIN10 polygon's state from its PIN14 rows.
* ``map_polygon_state`` is the map's rule.  It reuses ``classify`` and adds the two states the map needs and the
  census could not see: ``condo_building`` (the polygon holds unit PINs) and ``multi_pin_member`` (the building
  area on file is a multi-parcel complex's total, so it describes no single lot).
"""

from __future__ import annotations

from backend.provenance import FADE_COVERAGE_BELOW, HIDE_COVERAGE_BELOW

IMPLAUSIBLE_FAR_MULTIPLE = 3.0  # mirrors frontend/src/lib/scorecardVerdict.ts
MIN_LOT_SQFT = 500.0  # below this a lot area is a data fragment, not a lot
MAX_LOT_SQFT = 2_000_000.0

# Classes whose PIN14s are units inside a building: neither lot nor building area belongs to the unit.
CONDO_CLASSES = frozenset({"2-99", "5-99"})
EXEMPT_CLASSES = frozenset({"EX", "RR"})

# Capacity states, in precedence order.  Only COMPUTABLE may be colored as a utilization.
STATES = (
    "no_zoning",  # the parcel is outside the zoning polygons
    "planned_development",  # bulk is set by the ordinance, not the district table
    "condo_unit",  # a unit PIN; the building's area is not the unit's
    "exempt",  # tax-exempt or railroad: not a soft-site candidate by class
    "no_allowed_far",  # a district whose table row has no FAR (e.g. manufacturing)
    "unknown_land",  # lot area absent
    "suspect_land",  # lot area outside a plausible range
    "class_conflict",  # a vacant class that also carries a building area
    "vacant_land",  # vacant class, lot area known: nothing built
    "unknown_gfa",  # building area absent: never read as "underbuilt"
    "apparently_overbuilt",  # existing FAR far above the cap: data mismatch, not a legal finding
    "computable",
)

# The map's polygon states: the census states with ``condo_unit`` read at building level, plus the two the
# map adds.  ``no_base_row`` is a polygon whose PIN14s include no -0000 row, so no row speaks for the lot.
MAP_STATES = (
    "no_zoning",
    "planned_development",
    "condo_building",  # the polygon holds unit PINs: no unit row speaks for the building
    "exempt",
    "no_allowed_far",
    "unknown_land",
    "suspect_land",
    "class_conflict",
    "vacant_land",
    "multi_pin_member",  # the only building area on file is a multi-parcel complex's total
    "unknown_gfa",
    "apparently_overbuilt",
    "no_base_row",
    "computable",
)


def classify(attrs: dict) -> str:
    """One parcel's capacity state from its Discovery-index attributes.

    Unknown building area is its own state: it never becomes zero, never becomes "underbuilt".  An existing FAR
    above ``IMPLAUSIBLE_FAR_MULTIPLE`` times the cap is flagged, never ranked, and is not read as nonconformity."""
    zoning = attrs.get("zoning_group")
    cls = attrs.get("class") or ""
    land = attrs.get("land_sqft")
    bldg = attrs.get("bldg_sqft")
    far = attrs.get("density_band")
    if zoning is None:
        return "no_zoning"
    if zoning == "planned_development":
        return "planned_development"
    if cls in CONDO_CLASSES:
        return "condo_unit"
    if cls in EXEMPT_CLASSES:
        return "exempt"
    if not far:
        return "no_allowed_far"
    if land is None:
        return "unknown_land"
    if land < MIN_LOT_SQFT or land > MAX_LOT_SQFT:
        return "suspect_land"
    if attrs.get("is_vacant"):
        return "class_conflict" if bldg else "vacant_land"
    if not bldg:
        return "unknown_gfa"
    if bldg / land > IMPLAUSIBLE_FAR_MULTIPLE * far:
        return "apparently_overbuilt"
    return "computable"


def pin10(pin: str) -> str:
    """The base parcel of a formatted PIN14 ("14-33-103-011-0000" -> "14-33-103-011")."""
    return pin[:13]


def polygon_state(rows: list[tuple[str, dict]]) -> str:
    """The state of a map polygon (all PIN14s sharing a PIN10), as the Phase 0 census counts it.

    A building with unit PINs is a condo polygon whatever its base row says.  Otherwise the base row (suffix
    0000) speaks for the polygon; a polygon with no base row has no honest single state."""
    if any((a.get("class") or "") in CONDO_CLASSES for _, a in rows):
        return "condo_unit"
    for pin, attrs in rows:
        if pin.endswith("-0000"):
            return classify(attrs)
    return "no_base_row"


def map_polygon_state(attrs: dict, *, has_unit_pins: bool, complex_total_only: bool) -> str:
    """The map's state for one PIN10 polygon.

    ``attrs`` is the polygon's base row with the map's own inputs already in place (zoning group and allowed FAR
    from the polygon's district, building area from the index or the Commercial Valuation artifact).
    ``has_unit_pins``: any PIN14 on the PIN10 is a condo unit.  ``complex_total_only``: the index has no
    building area and the artifact's area belongs to a complex spanning more than one PIN10.

    The two map states slot into the census order where their census twin would land: ``condo_building`` where
    ``condo_unit`` is, and ``multi_pin_member`` just before ``unknown_gfa`` (it *is* an unknown building area,
    with a reason), so a parcel that is, say, exempt stays exempt."""
    state = classify(attrs)
    if has_unit_pins and state not in ("no_zoning", "planned_development"):
        return "condo_building"
    if state == "condo_unit":
        return "condo_building"
    if state == "unknown_gfa" and complex_total_only:
        return "multi_pin_member"
    return state


def coverage_verdict(share: float) -> str:
    """The confidence standard's coverage states applied to the share of computable parcels."""
    if share < HIDE_COVERAGE_BELOW:
        return "withheld"
    if share < FADE_COVERAGE_BELOW:
        return "low"
    return "standard"
