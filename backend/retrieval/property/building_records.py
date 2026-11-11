"""What each source says about the building, side by side (the new UI's History tab, decision Item 103).

The Profile's summary keeps one value per building fact: the Assessor's when it has one, else the first fallback
that answers (``_build_summary``: fill-only, with a ``*_source`` label), so a disagreement between sources is
invisible. The brief asks for it to show ("built 1928–31 · records differ"). This asks the City's building
footprints (and, for a parcel outside the Assessor's residential characteristics, the County's Commercial
Valuation) even when the summary has no gap, and lists every source's value for year built, stories and floor area.

Only the Profile's parts fetch this (``next_ui.building_records``); the full ``/api/scorecard``, chat grounding and
the report are unchanged. Every source here is cached a day by its own module.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

FACTS = ("year_built", "stories", "bldg_sqft")

# When two sources' values count as different (owner-facing rule, decision Item 103): years two or more apart (a
# one-year gap is an assessment-year rounding, not a disagreement), a whole story or more, floor areas 15% or more
# apart (footprint areas are traced from aerials; the Assessor's from its records).
YEAR_GAP = 2
STORY_GAP = 1.0
AREA_RATIO = 0.15


def _num(v: Any) -> float | None:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _spans_lots(prop: Any, footprint_sqft: Any) -> bool:
    """``_build_summary``'s footprint rule: a footprint larger than the lot by ``_FOOTPRINT_SPAN_SLACK`` belongs to a
    building that spans several lots, so its area isn't this lot's."""
    from backend.retrieval.property import _FOOTPRINT_SPAN_SLACK

    land, area = _num(getattr(prop, "land_sqft", None)), _num(footprint_sqft)
    return bool(land and area and area > land * _FOOTPRINT_SPAN_SLACK)


def differs(fact: str, values: list[float]) -> bool:
    """Whether a fact's values from different sources disagree, by the rule above."""
    if len(values) < 2:
        return False
    lo, hi = min(values), max(values)
    if fact == "year_built":
        return hi - lo >= YEAR_GAP
    if fact == "stories":
        return hi - lo >= STORY_GAP
    return (hi - lo) / lo >= AREA_RATIO


async def building_records(prop: Any, lat: float, lon: float) -> dict[str, Any] | None:
    """Every source's value per building fact: ``{"facts": {fact: [{source, value, as_of}]}, "differ": [fact],
    "unanswered": [source]}``. None for a parcel with no building to describe (vacant land, class 1xx) or no
    property record."""
    if prop is None:
        return None
    cls = str(getattr(prop, "bldg_class", None) or "")
    if cls.startswith("1"):
        return None

    from backend.retrieval.property.building_facts import get_commercial_facts, get_footprint_facts

    facts: dict[str, list[dict[str, Any]]] = {f: [] for f in FACTS}

    def add(fact: str, source: str, value: Any, as_of: int | None = None) -> None:
        n = _num(value)
        if n is None:
            return
        for e in facts[fact]:
            if e["source"] == source:  # the summary's own entry: keep its value, take the source's date
                e["as_of"] = e["as_of"] or as_of
                return
        facts[fact].append({"source": source, "value": int(n) if fact != "stories" else n, "as_of": as_of})

    # The summary's own values first, under the source it named.
    for f in FACTS:
        src = getattr(prop, f"{f}_source", None)
        if src:
            add(f, src, getattr(prop, f, None))

    coros: dict[str, Any] = {
        "footprint": get_footprint_facts(lat, lon, parcel_geojson=getattr(prop, "parcel_geometry", None)),
    }
    # x54s (the Assessor's residential characteristics) covers class 2xx; the Commercial Valuation covers the rest.
    pin14 = getattr(prop, "pin14", None)
    if pin14 and not cls.startswith("2"):
        coros["commercial_valuation"] = get_commercial_facts(pin14)
    got = await asyncio.gather(*coros.values(), return_exceptions=True)
    unanswered: list[str] = []
    for name, value in zip(coros, got):
        if isinstance(value, BaseException):
            if not isinstance(value, Exception):
                raise value
            log.warning("Building records %s failed: %s", name, value)
            unanswered.append(name)
            continue
        if not value:
            continue
        as_of = value.get("valuation_year") if name == "commercial_valuation" else None
        for f in FACTS:
            if f == "bldg_sqft" and name == "footprint" and _spans_lots(prop, value.get(f)):
                continue  # the Profile's own rule: a footprint this much larger than the lot is a building on several lots
            add(f, name, value.get(f), as_of)

    energy = getattr(prop, "energy", None)
    if energy is not None:
        add("year_built", "energy_benchmark", getattr(energy, "year_built", None), getattr(energy, "data_year", None))
        add("bldg_sqft", "energy_benchmark", getattr(energy, "gross_floor_area", None), getattr(energy, "data_year", None))

    return {
        "facts": facts,
        "differ": [f for f in FACTS if differs(f, [e["value"] for e in facts[f]])],
        "unanswered": unanswered,
    }
