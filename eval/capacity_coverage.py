"""WS8 Phase 0: for which parcels can we honestly say how much of the allowed floor area is built?

No model calls and nothing is served.  This reads a Discovery index file read-only and answers, with counts:

  A. Per community area and citywide: the share of parcels with lot area, building area and an allowed FAR,
     and the share that lands in each capacity state (see ``classify``).
  B. The same census at map-polygon level (PIN10), because a condo building is one polygon carrying many
     PIN14s and a block map draws polygons, not rows.
  C. Per community area, whether utilization could be colored or must be withheld, using the confidence
     standard's coverage thresholds (guides/source-confidence.md section 3).
  D. How many index rows lie outside every community-area polygon.  The builder fetches each area by bounding
     box and keeps the box's area when the point is in no polygon (``community_area_by_point(...) or ca``), so
     suburban parcels carry a Chicago community-area tag.  They are counted here and excluded from A-C.

The index's building area comes from the Assessor's regression-class characteristics only; the Profile's
fallback chain (condo, commercial valuation, energy, footprints) is measured separately (slices 2 and 3).

Usage:  PYTHONPATH=. python -m eval.capacity_coverage --index <discovery_index.db> \
            [--out eval/results/2026-10-28-ws8/index_census.json]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable

HIDE_COVERAGE_BELOW = 0.10  # mirrors backend/provenance.py (a test pins the agreement)
FADE_COVERAGE_BELOW = 0.25
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
    """The state of a map polygon (all PIN14s sharing a PIN10).

    A building with unit PINs is a condo polygon whatever its base row says.  Otherwise the base row (suffix
    0000) speaks for the polygon; a polygon with no base row has no honest single state."""
    if any((a.get("class") or "") in CONDO_CLASSES for _, a in rows):
        return "condo_unit"
    for pin, attrs in rows:
        if pin.endswith("-0000"):
            return classify(attrs)
    return "no_base_row"


def coverage_verdict(share: float) -> str:
    """The confidence standard's coverage states applied to the share of computable parcels."""
    if share < HIDE_COVERAGE_BELOW:
        return "withheld"
    if share < FADE_COVERAGE_BELOW:
        return "low"
    return "standard"


def _blank() -> dict:
    return {"n": 0, "land": 0, "bldg": 0, "far": 0, "all_three": 0, "states": Counter()}


def _tally(bucket: dict, attrs: dict, state: str) -> None:
    bucket["n"] += 1
    has_land = attrs.get("land_sqft") is not None
    has_bldg = attrs.get("bldg_sqft") is not None
    has_far = attrs.get("density_band") is not None
    bucket["land"] += has_land
    bucket["bldg"] += has_bldg
    bucket["far"] += has_far
    bucket["all_three"] += has_land and has_bldg and has_far
    bucket["states"][state] += 1


def _ca_of(regions: str) -> int | None:
    for r in json.loads(regions):
        if r.startswith("neighborhood:"):
            return int(r.split(":", 1)[1])
    return None


def _share(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _render(bucket: dict) -> dict:
    n = bucket["n"]
    out = {
        "n": n,
        "land_share": _share(bucket["land"], n),
        "bldg_share": _share(bucket["bldg"], n),
        "far_share": _share(bucket["far"], n),
        "all_three_share": _share(bucket["all_three"], n),
        "states": {s: bucket["states"].get(s, 0) for s in STATES},
        "state_shares": {s: _share(bucket["states"].get(s, 0), n) for s in STATES},
    }
    out["states"].update({s: c for s, c in bucket["states"].items() if s not in out["states"]})  # e.g. no_base_row
    computable = _share(bucket["states"].get("computable", 0), n)
    out["verdict"] = coverage_verdict(computable)
    return out


def census(rows: Iterable[tuple[str, float, float, str, str]], locate: Callable[[float, float], int | None]) -> dict:
    """``rows`` are (pin, lat, lon, attrs JSON, regions JSON) as stored in the index; ``locate`` maps a point to
    its community area (None outside the city).  Rows outside the city are counted apart and left out of every
    share, so a suburb never lowers a Chicago community area's coverage."""
    rows_by_ca: dict[int | None, dict] = defaultdict(_blank)
    poly_by_ca: dict[int | None, dict] = defaultdict(_blank)
    city_rows, city_poly = _blank(), _blank()
    by_poly: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    poly_ca: dict[str, int | None] = {}
    outside = {"n": 0, "tagged_to_ca": Counter(), "pin_prefix": Counter()}
    total = 0
    for pin, lat, lon, attrs_json, regions in rows:
        total += 1
        if locate(lat, lon) is None:
            outside["n"] += 1
            outside["tagged_to_ca"][str(_ca_of(regions))] += 1
            outside["pin_prefix"][pin[:2]] += 1
            continue
        attrs = json.loads(attrs_json)
        ca = _ca_of(regions)
        state = classify(attrs)
        _tally(rows_by_ca[ca], attrs, state)
        _tally(city_rows, attrs, state)
        key = pin10(pin)
        by_poly[key].append((pin, attrs))
        poly_ca.setdefault(key, ca)
    for key, members in by_poly.items():
        state = polygon_state(members)
        base = next((a for p, a in members if p.endswith("-0000")), members[0][1])
        _tally(poly_by_ca[poly_ca[key]], base, state)
        _tally(city_poly, base, state)

    def by_ca(buckets: dict) -> dict:
        return {str(k): _render(v) for k, v in sorted(buckets.items(), key=lambda kv: (kv[0] is None, kv[0]))}

    return {
        "index_rows": total,
        "outside_city": {
            "n": outside["n"],
            "share_of_index": _share(outside["n"], total),
            "tagged_to_ca": dict(outside["tagged_to_ca"].most_common()),
            "pin_prefix": dict(outside["pin_prefix"].most_common()),
        },
        "rows": {"citywide": _render(city_rows), "by_community_area": by_ca(rows_by_ca)},
        "polygons": {"citywide": _render(city_poly), "by_community_area": by_ca(poly_by_ca)},
    }


def read_index(path: Path) -> tuple[dict, Iterable[tuple[str, float, float, str, str]]]:
    """Open the index read-only; returns (meta, row iterator)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    meta = con.execute("select * from meta").fetchone()
    info = {"index_id": meta[0], "built_at": meta[1], "community_areas": meta[2], "parcel_count": meta[3]}
    return info, con.execute("select pin, lat, lon, attrs, regions from parcels")


def _names() -> dict[int, str]:
    from backend.retrieval.geo import COMMUNITY_AREAS

    return dict(COMMUNITY_AREAS)


def summary_lines(result: dict, level: str = "polygons") -> list[str]:
    names = _names()
    block = result[level]
    city = block["citywide"]
    lines = [f"{level} citywide n={city['n']}: land {city['land_share']:.1%} bldg {city['bldg_share']:.1%} "
             f"far {city['far_share']:.1%} all-three {city['all_three_share']:.1%}"]
    for s in STATES:
        lines.append(f"  {s:22s} {city['states'].get(s, 0):>8d} {city['state_shares'][s]:7.1%}")
    verdicts = Counter(v["verdict"] for v in block["by_community_area"].values())
    lines.append(f"  community-area verdicts: {dict(verdicts)}")
    ranked = sorted(block["by_community_area"].items(), key=lambda kv: kv[1]["state_shares"]["computable"])
    for ca, v in ranked[:5] + ranked[-5:]:
        lines.append(f"  CA {ca:>3} {names.get(int(ca), '?') if ca != 'None' else '?':24s} computable {v['state_shares']['computable']:6.1%} {v['verdict']}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, required=True, help="a Discovery index SQLite file (opened read-only)")
    ap.add_argument("--out", type=Path, help="write the full result as JSON")
    args = ap.parse_args()
    info, rows = read_index(args.index)
    from backend.retrieval.geo import community_area_by_point

    result = {"index": info, **census(rows, community_area_by_point)}
    out = result["outside_city"]
    print(f"index rows {result['index_rows']}: outside every community-area polygon {out['n']} ({out['share_of_index']:.1%}); "
          f"top tagged areas {dict(list(out['tagged_to_ca'].items())[:6])}")
    for level in ("rows", "polygons"):
        print("\n".join(summary_lines(result, level)))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True))
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
