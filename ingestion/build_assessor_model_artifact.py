"""Build ``assessor_model_by_area.json``: the Assessor's modeled apartment income per community area.

WS4 PR3.  The Cook County Assessor values buildings of 7+ units with an income model (Commercial Valuation,
``csik-bsws``): a potential gross income (PGI, before vacancy) and a unit mix per building.  This script turns
the Chicago rows of the latest city reassessment into one row per community area:

* ``median_pgi_per_unit_month`` = the median over buildings of ``pgi / tot_units / 12``.  It is the Assessor's
  *modeled* income, never an asking or achieved rent, and there is no rent by bedroom (the unit mix is counts).
* ``units`` / ``households``: modeled units against the area's ACS renter households with cash rent (read from
  ``rent_by_area.json``, so no Census key is needed here).  Their ratio is the series' coverage; whether it is
  shown, faded or withheld is decided at serve time by ``provenance.confidence_state``, not here.

Only ``Multifamily-*`` property types count.  Hotels and care homes carry a "units" count (rooms and beds) but no
income model: left in, they inflate the units without adding income (66,325 units; the Loop reads 231% with
them, 124% without).  Decision Item 35.

The Assessor values one triad a year, so the newest year holds a slice of the city; the city's multifamily stock
is in the city-wide reassessment years (2021, 2024, next 2027).  The builder uses the newest year with at least
``MIN_CITY_ROWS`` rows and records it, so the Profile can say "2024 city reassessment" and the age rule can fire.

Usage:  PYTHONPATH=. python -m ingestion.build_assessor_model_artifact
Production never runs this; it reads the committed artifact.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

from eval import rent_method as rm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "assessor_model_by_area.json"
META_PATH = OUTPUT_PATH.with_name("assessor_model_by_area.meta.json")
RENT_ARTIFACT = PROJECT_ROOT / "ingestion" / "data" / "rent_by_area.json"

CHICAGO_TOWNSHIPS = ("Rogers Park", "West Chicago", "Lake View", "South Chicago", "Hyde Park", "North Chicago", "Lake", "Jefferson")
MIN_CITY_ROWS = 5000  # a city-wide reassessment year (2024: 11,016); a single triad's year is ~1,400
PROPERTY_TYPE_PREFIX = "Multifamily"
COLUMNS = "keypin,tot_units,pgi,property_type_use"
PIN_BATCH = 400


def is_apartment(row: dict) -> bool:
    """Apartment buildings only: the Assessor's own property type starts with ``Multifamily``."""
    return str(row.get("property_type_use") or "").startswith(PROPERTY_TYPE_PREFIX)


def summarize(rows: list[dict], area_of: dict[str, str], households: dict[str, int]) -> dict[str, dict]:
    """``csik-bsws`` rows + ``{pin: community area}`` + ``{area: households}`` -> one row per community area.

    A building counts when it is an apartment building with units and a positive modeled income (``priced``).
    ``units`` sums only those buildings, so coverage and the median describe the same buildings. A building
    that cannot be placed in a community area is left out and counted in the builder's ``unmatched``."""
    per: dict[str, dict] = defaultdict(lambda: {"buildings": 0, "units": 0.0, "pgi_per_unit_month": []})
    for r in rows:
        if not is_apartment(r):
            continue
        area = area_of.get(str(r.get("keypin", "")).replace("-", ""))
        units, pgi = rm._num(r.get("tot_units")), rm._num(r.get("pgi"))
        if area is None or not units or units <= 0:
            continue
        a = per[area]
        a["buildings"] += 1
        if pgi and pgi > 0:
            a["units"] += units
            a["pgi_per_unit_month"].append(pgi / units / 12.0)
    out = {}
    for area, a in sorted(per.items(), key=lambda kv: int(kv[0])):
        priced = a["pgi_per_unit_month"]
        out[area] = {
            "buildings": a["buildings"],
            "priced": len(priced),
            "units": round(a["units"]),
            "households": households.get(area),
            "median_pgi_per_unit_month": round(statistics.median(priced)) if priced else None,
        }
    return out


def _pull(client: httpx.Client, where: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = rm.socrata(client, rm.COMMERCIAL_VALUATION, **{
            "$select": COLUMNS, "$where": where, "$limit": "10000", "$offset": str(offset), "$order": "keypin"})
        rows += page
        if len(page) < 10000:
            return rows
        offset += 10000


def build() -> tuple[dict, dict]:
    towns = ",".join(repr(t) for t in CHICAGO_TOWNSHIPS)
    households = {a: int(v["households"]) for a, v in json.loads(RENT_ARTIFACT.read_text())["community_areas"].items()}
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        by_year = rm.socrata(client, rm.COMMERCIAL_VALUATION, **{
            "$select": "year,count(*)", "$where": f"tot_units>0 AND township in ({towns})",
            "$group": "year", "$order": "year DESC"})
        year = next((r["year"] for r in by_year if int(r["count"]) >= MIN_CITY_ROWS), None)
        if year is None:
            raise RuntimeError(f"no Commercial Valuation year has {MIN_CITY_ROWS}+ Chicago rows with units: {by_year[:4]}")
        rows = _pull(client, f"year='{year}' AND tot_units>0 AND township in ({towns})")
        apartments = [r for r in rows if is_apartment(r)]
        pins = sorted({r["keypin"].replace("-", "") for r in apartments})
        area_of: dict[str, str] = {}
        for i in range(0, len(pins), PIN_BATCH):
            chunk = pins[i:i + PIN_BATCH]
            got = rm.socrata(client, rm.PARCEL_UNIVERSE, **{
                "$select": "pin,chicago_community_area_num",
                "$where": f"pin in ({','.join(repr(p) for p in chunk)}) AND chicago_community_area_num IS NOT NULL",
                "$order": "year DESC", "$limit": "5000"})
            for g in got:
                area_of.setdefault(g["pin"], g["chicago_community_area_num"])
    areas = summarize(rows, area_of, households)
    unmatched = sum(1 for r in apartments if r["keypin"].replace("-", "") not in area_of)
    artifact = {
        "assessor": {
            "dataset": "csik-bsws", "year": year, "cycle": "city reassessment", "as_of": f"{year}-12-31",
            "property_types": f"{PROPERTY_TYPE_PREFIX}-*", "measure": "potential gross income per unit per month (before vacancy)",
        },
        "universe": {"label": "renter households with cash rent", "source": "rent_by_area.json (ACS B25063)"},
        "community_areas": areas,
    }
    meta = {
        "built_at": date.today().isoformat(), "assessor_year": year, "community_areas": len(areas),
        "buildings": sum(a["buildings"] for a in areas.values()), "unmatched_to_community_area": unmatched,
        "builder": "ingestion/build_assessor_model_artifact.py",
    }
    return artifact, meta


def main() -> None:
    artifact, meta = build()
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=0, sort_keys=True, separators=(",", ":")) + "\n")
    META_PATH.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} ({OUTPUT_PATH.stat().st_size} bytes): "
          f"{meta['community_areas']} community areas, {meta['buildings']} apartment buildings, "
          f"Assessor {meta['assessor_year']} ({meta['unmatched_to_community_area']} unmatched)")


if __name__ == "__main__":
    main()
