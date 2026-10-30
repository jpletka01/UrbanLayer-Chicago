"""Build ``rent_by_area.json``: official overall rent per community area, plus the tract -> PUMA lookup.

WS4 PR2.  Production never calls the Census API (it needs a key), so what it needs from aggregation is
built here, offline, and committed:

* **Overall median gross rent per community area**, rebuilt from the summed tract rent-bracket counts of
  ACS table B25063 (medians are not additive) with the ACS Handbook's margin of error for an interpolated
  median.  Method proof and evidence: ``eval/rent_method.py`` and decision Item 33.  Whether a figure is
  shown, faded or withheld is NOT decided here: ``provenance.confidence_state`` reads the coefficient of
  variation at serve time.
* **Tract -> PUMA** from the Assessor's tags in Parcel Universe, so the request path can name the PUMA whose
  published bedroom medians stand in for a tract the Census suppresses (PUMAs nest tracts; they do not nest in
  community areas, so a PUMA figure is never labeled as a community area's).

Needs ``CENSUS_API_KEY`` in ``.env`` (read, never printed).  Writes the artifact and its ``.meta.json`` sidecar
(the data-health probe and ``backend.data_health.artifacts`` read the build date from it).

Usage:  PYTHONPATH=. python -m ingestion.build_rent_artifact [--year 2024]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import httpx

from eval import rent_method as rm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "rent_by_area.json"
META_PATH = OUTPUT_PATH.with_name("rent_by_area.meta.json")

# The Handbook's standard error scales with the table's design factor, which the Census publishes per table
# and state.  B25063's has not been looked up (decision Item 33, "not settled"), so the cautious end of the
# measured range is used: at 1.5 areas 12, 37, 47, 54 and 55 fade or are withheld; at 1.0 only 37 and 47.
DESIGN_FACTOR = 1.5
MOE_METHOD = "acs_handbook_median"


def tract_lookup(rows: list[tuple[str, str, str, int]]) -> dict[str, dict]:
    """``(tract, puma, community area, residential parcels)`` rows -> ``{tract: {"puma", "ca"}}``.

    Each tract goes to the community area and the PUMA holding most of its residential parcels.  PUMAs are
    unions of tracts, so a tract split across two PUMAs means the Assessor's tags disagree: that is an error.
    """
    by_tract_ca: dict[str, Counter] = defaultdict(Counter)
    by_tract_puma: dict[str, Counter] = defaultdict(Counter)
    for tract, puma, ca, n in rows:
        by_tract_ca[tract][ca] += n
        by_tract_puma[tract][puma] += n
    out = {}
    for tract in sorted(by_tract_ca):
        pumas = by_tract_puma[tract]
        if len(pumas) > 1:
            raise ValueError(f"tract {tract} is tagged to more than one PUMA: {dict(pumas)}")
        out[tract] = {"puma": next(iter(pumas)), "ca": by_tract_ca[tract].most_common(1)[0][0]}
    return out


def area_rent(rows: list[dict], cols: list[tuple[str, tuple[float, float | None]]]) -> dict:
    """One community area: summed bracket counts -> interpolated median and its Handbook margin (90%)."""
    summed = [sum(rm._num(r.get(f"{v}E")) or 0.0 for r in rows) for v, _ in cols]
    brackets = [(lo, hi, c) for (_, (lo, hi)), c in zip(cols, summed, strict=True)]
    median = rm.bracket_median(brackets)
    moe = rm.handbook_median_moe(brackets, DESIGN_FACTOR) if median is not None else None
    return {
        "households": round(sum(summed)),
        "median": None if median is None else round(median),
        "moe": None if moe is None else round(moe),
        "top_coded": median is None and sum(summed) > 0,
    }


def build(year: int) -> tuple[dict, dict]:
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        pu_year = rm.socrata(client, rm.PARCEL_UNIVERSE, **{"$select": "max(year)"})[0]["max_year"]
        parcels = rm.socrata(client, rm.PARCEL_UNIVERSE, **{
            "$select": "census_acs5_tract_geoid,census_acs5_puma_geoid,chicago_community_area_num,count(*)",
            "$where": (f"year='{pu_year}' AND chicago_community_area_num IS NOT NULL AND census_acs5_tract_geoid IS NOT NULL"
                       " AND census_acs5_puma_geoid IS NOT NULL AND (starts_with(class,'2') OR starts_with(class,'3'))"),
            "$group": "census_acs5_tract_geoid,census_acs5_puma_geoid,chicago_community_area_num", "$limit": "50000"})
        tracts = tract_lookup([(r["census_acs5_tract_geoid"], r["census_acs5_puma_geoid"],
                                r["chicago_community_area_num"], int(r["count"])) for r in parcels])
        # the community area's tracts are the dominant-area ones (decision Item 33, Decision 3)
        by_area: dict[str, list[str]] = defaultdict(list)
        for tract, t in tracts.items():
            by_area[t["ca"]].append(tract)
        geo_in = "state:17 county:031"
        rows63 = {rm._tract_geoid(r): r for r in rm.census_group(client, year, "B25063", "tract:*", geo_in)}
        cols = rm._bracket_columns(rm.census_labels(client, year, "B25063"))
        areas = {a: area_rent([rows63[t] for t in ts if t in rows63], cols) for a, ts in sorted(by_area.items(), key=lambda kv: int(kv[0]))}
    period = f"{year - 4}–{year}"
    artifact = {
        "acs": {"release": f"acs{year}_5yr", "period": period, "period_end": f"{year}-12-31", "table": "B25063"},
        "method": {"key": MOE_METHOD, "design_factor": DESIGN_FACTOR, "tract_assignment": "dominant residential parcels (Parcel Universe)"},
        "parcel_universe_year": pu_year,
        "community_areas": areas,
        "tract_puma": {t: v["puma"] for t, v in tracts.items()},
    }
    meta = {"built_at": date.today().isoformat(), "acs_release": artifact["acs"]["release"], "acs_period": period,
            "community_areas": len(areas), "tracts": len(tracts), "design_factor": DESIGN_FACTOR,
            "builder": "ingestion/build_rent_artifact.py"}
    return artifact, meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--year", type=int, default=2024, help="ACS 5-year release (period ends this year)")
    args = ap.parse_args()
    artifact, meta = build(args.year)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=0, sort_keys=True, separators=(",", ":")) + "\n")
    META_PATH.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} ({OUTPUT_PATH.stat().st_size} bytes): "
          f"{meta['community_areas']} community areas, {meta['tracts']} tracts, ACS {meta['acs_period']}")


if __name__ == "__main__":
    main()
