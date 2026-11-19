"""Build ``new_construction_price.json``: what a new condo sells for per square foot, by community area (Item 124).

The Deep analysis tab prices a project's gross floor area. Its old starting sale price was the area's median condo of
any size or age, per unit, so a new 3-flat bid almost nothing for its land. This is the measured replacement:

* **The area's condo price level:** the median arm's-length condo sale per gross square foot, 2023-2025, any age
  (``eval.new_construction_price``: Assessor sales, the unit's share of the building = building sq ft x ownership
  share). An area with fewer than ``MIN_N`` sales borrows its nearest areas (by centroid) until it has them, and says so.
* **The new-construction premium:** each condo's first sale (within five years of being built, Item 133) over its
  own area's level, citywide. Its median and middle half set the starting figure and its band.
* **The whole building (2-6 units, Item 133):** the same two steps on 2-6 unit buildings, per building sq ft: the
  area's 2-6 unit level (any age) x the premium of a new building's first sale after it was built. Kept under each
  area's ``building`` key; never compared with the condo figure per sq ft (different square-foot bases).

Measured 2026-11-16 (Item 124): premium 1.16 on condos sold within two years (n 71). Item 133 has the first-sale
numbers.

No model calls; public Socrata reads (~15 min cold; ``--cache`` keeps the raw pulls).

Usage:  PYTHONPATH=. python -m ingestion.build_new_construction_artifact [--cache DIR/raw_sales.json]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import date
from pathlib import Path

from eval.new_construction_price import measure

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "new_construction_price.json"
META_PATH = OUTPUT_PATH.with_name("new_construction_price.meta.json")
AREAS_PATH = PROJECT_ROOT / "ingestion" / "data" / "community_areas.geojson"
MIN_N = 30


def _centroids() -> dict[str, tuple[float, float]]:
    """A rough centroid per community area (the mean of its outer rings' vertices; enough to rank neighbors)."""
    out: dict[str, tuple[float, float]] = {}
    for f in json.loads(AREAS_PATH.read_text())["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        pts = [p for poly in polys for p in poly[0]]
        out[str(f["properties"]["community_area"])] = (
            sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return out


def _miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = (a[0] - b[0]) * 69.17 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot(dx, (a[1] - b[1]) * 69.17)


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    v = sorted(values)
    q = statistics.quantiles(v, n=4)
    return q[0], statistics.median(v), q[2]


def _bands(res: dict, group: str, cents: dict[str, tuple[float, float]]) -> tuple[dict, dict[str, dict]]:
    """One group's premium and every area's figure: the area's any-age level per sq ft (pooled with its nearest
    areas below ``MIN_N`` sales) x the citywide premium of new sales over their own area's level."""
    records = res["records"]
    key = f"{group}_any_age"
    any_age = {ca: v[key]["per_sqft"] for ca, v in res["community_areas"].items() if key in v}

    # The premium: each new sale over its own area's any-age median (areas with a reliable median only).
    ratios = [psf / any_age[ca]["median"] for ca, g, _y, psf in records
              if g == group and ca in any_age and any_age[ca]["n"] >= MIN_N]
    p25, med, p75 = _quartiles(ratios)

    new_here: dict[str, int] = {}
    for ca, g, _y, _psf in records:
        if g == group:
            new_here[ca] = new_here.get(ca, 0) + 1

    areas: dict[str, dict] = {}
    for ca in sorted(cents, key=int):
        if ca in any_age and any_age[ca]["n"] >= MIN_N:
            level, n, used = any_age[ca]["median"], any_age[ca]["n"], [ca]
        else:
            # Nearest areas first until the pooled sales reach MIN_N; the level is the sales-weighted median of
            # their medians (the measurement keeps medians, not every sale).
            near = sorted((c for c in any_age if c != ca), key=lambda c: _miles(cents[ca], cents[c]))
            used, n = ([ca] if ca in any_age else []), (any_age[ca]["n"] if ca in any_age else 0)
            for c in near:
                if n >= MIN_N:
                    break
                used.append(c)
                n += any_age[c]["n"]
            weighted = sorted((any_age[c]["median"], any_age[c]["n"]) for c in used)
            half, acc = n / 2, 0
            level = weighted[-1][0]
            for m, k in weighted:
                acc += k
                if acc >= half:
                    level = m
                    break
        areas[ca] = {
            "level": round(level), "n": n, "areas": used if used != [ca] else None,
            "value": round(level * med), "low": round(level * p25), "high": round(level * p75),
            # New sales in this area itself in the window; 0 = the premium is carried over from other areas.
            "new_sales": new_here.get(ca, 0),
        }
    premium = {"median": round(med, 3), "p25": round(p25, 3), "p75": round(p75, 3), "n": len(ratios)}
    return premium, areas


def build(res: dict) -> tuple[dict, dict]:
    cents = _centroids()
    premium, condo = _bands(res, "condo", cents)
    building_premium, building = _bands(res, "two_to_six", cents)
    areas = {ca: {**row, "building": building[ca]} for ca, row in condo.items()}
    first, last = res["years"]
    artifact = {
        "unit": "usd_per_gross_sqft",
        "years": [str(first), str(last)],
        "max_age": res["max_age"],
        "condo_max_age": res.get("condo_max_age"),
        "premium": premium,
        "building_premium": building_premium,
        "min_n": MIN_N,
        "method": ("condos: area condo median per gross sq ft (any age) x the citywide premium of a unit's first sale "
                   "within condo_max_age years of being built; gross sq ft = building sq ft x the unit's ownership "
                   "share. building (2-6 units): area 2-6 unit median per building sq ft (any age) x the premium of "
                   "a building's first sale on or after its year built, within max_age years"),
        "source": ("Cook County Assessor sales wvhk-k5uv + condo characteristics 3r7i-mrz4 + residential "
                   "characteristics x54s-btds + Parcel Universe pabr-t5kh"),
        "community_areas": areas,
    }
    meta = {"built_at": date.today().isoformat(), "years": artifact["years"], "premium": premium,
            "building_premium": building_premium, "community_areas": len(areas),
            "pooled": sum(1 for a in areas.values() if a["areas"]),
            "with_new_sales": sum(1 for a in areas.values() if a["new_sales"]),
            "building_pooled": sum(1 for a in areas.values() if a["building"]["areas"]),
            "building_with_new_sales": sum(1 for a in areas.values() if a["building"]["new_sales"]),
            "builder": "ingestion/build_new_construction_artifact.py"}
    return artifact, meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--first", type=int, default=2023)
    ap.add_argument("--last", type=int, default=date.today().year - 1)
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--from-json", type=Path, help="a saved eval.new_construction_price result instead of fetching")
    a = ap.parse_args()
    res = json.loads(a.from_json.read_text()) if a.from_json else measure(a.first, a.last, 2, a.cache)
    artifact, meta = build(res)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=1, sort_keys=True) + "\n")
    META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
