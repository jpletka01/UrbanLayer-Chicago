"""Build ``commercial_bldg_by_pin.json.gz``: the Assessor's building area per economic unit, for the capacity map.

WS8 Phase 1, data path (a) of decision Item 36.  The Discovery index carries the Assessor's characteristics
building area, which covers houses and small apartment buildings; commercial and large multifamily buildings are
valued from Commercial Valuation (``csik-bsws``) instead, so the index leaves them without a building area.  The
Profile fetches that dataset per parcel; a map of a block cannot (hundreds of calls per view), so this script pulls
the Chicago rows of the latest city-wide reassessment once and commits them.

One entry per economic unit (``keypin``):

* ``bldg_sqft``: the sum of ``bldgsf`` over the unit's rows of that year.  The dataset holds one row per building
  (and, for a split-class property, one row per class portion: retail and apartments), so the sum is the unit's
  floor area.  It is the same rule as the Profile's ``building_facts.get_commercial_facts``, so the map and the
  Profile agree.  ``None`` when no row of the unit carries an area.
* ``pins``: the unit's member PIN14s (the dataset's ``pins`` list; the keypin alone when the list is empty).  A
  unit whose members span more than one PIN10 describes a complex, not a lot: the loader never attributes its total
  to one member's polygon (Item 39).

Only one year is used: the newest with at least ``MIN_CITY_ROWS`` Chicago rows (the Assessor values one triad a
year, so a single triad's year would cover a third of the city).  A unit with no area in that year has no area here,
even if an older year had one; the Profile's per-parcel fetch falls back to older years, this artifact does not.

Usage:  PYTHONPATH=. python -m ingestion.build_commercial_bldg_artifact
Production never runs this; it reads the committed artifact.
"""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

from eval import rent_method as rm
from ingestion.build_assessor_model_artifact import CHICAGO_TOWNSHIPS, MIN_CITY_ROWS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "commercial_bldg_by_pin.json.gz"
META_PATH = OUTPUT_PATH.with_name("commercial_bldg_by_pin.meta.json")
COLUMNS = "keypin,pins,bldgsf"
PAGE = 10000


def _undash(pin: str) -> str:
    return pin.replace("-", "").strip()


def _area(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def summarize(rows: list[dict]) -> list[list]:
    """``csik-bsws`` rows of one year -> ``[[keypin, bldg_sqft | None, [member pins]], ...]`` sorted by keypin.

    PINs are 14 digits without dashes.  The member list always includes the keypin."""
    area: dict[str, float] = defaultdict(float)
    has_area: set[str] = set()
    members: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        key = _undash(str(r.get("keypin") or ""))
        if not key:
            continue
        members[key].add(key)
        members[key] |= {_undash(p) for p in str(r.get("pins") or "").split(",") if p.strip()}
        sqft = _area(r.get("bldgsf"))
        if sqft is not None:
            area[key] += sqft
            has_area.add(key)
    return [[k, round(area[k]) if k in has_area else None, sorted(members[k])] for k in sorted(members)]


def _pull(client: httpx.Client, where: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = rm.socrata(client, rm.COMMERCIAL_VALUATION, **{
            "$select": COLUMNS, "$where": where, "$limit": str(PAGE), "$offset": str(offset), "$order": "keypin"})
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE


def build() -> tuple[dict, dict]:
    towns = ",".join(repr(t) for t in CHICAGO_TOWNSHIPS)
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        by_year = rm.socrata(client, rm.COMMERCIAL_VALUATION, **{
            "$select": "year,count(*)", "$where": f"township in ({towns})", "$group": "year", "$order": "year DESC"})
        year = next((r["year"] for r in by_year if int(r["count"]) >= MIN_CITY_ROWS), None)
        if year is None:
            raise RuntimeError(f"no Commercial Valuation year has {MIN_CITY_ROWS}+ Chicago rows: {by_year[:4]}")
        rows = _pull(client, f"year='{year}' AND township in ({towns})")
    units = summarize(rows)
    member_count: dict[str, int] = defaultdict(int)
    for _, _, pins in units:
        for p in pins:
            member_count[p] += 1
    artifact = {
        "assessor": {"dataset": "csik-bsws", "year": year, "cycle": "city reassessment", "as_of": f"{year}-12-31",
                     "measure": "building area (sum of bldgsf over the economic unit's rows)"},
        "columns": ["keypin", "bldg_sqft", "pins"],
        "units": units,
    }
    meta = {
        "built_at": date.today().isoformat(), "assessor_year": year, "rows": len(rows), "units": len(units),
        "units_with_area": sum(1 for _, a, _ in units if a is not None),
        "multi_pin_units": sum(1 for _, _, pins in units if len(pins) > 1),
        "multi_pin10_units": sum(1 for _, _, pins in units if len({p[:10] for p in pins}) > 1),
        "member_pins": len(member_count),
        "pins_in_more_than_one_unit": sum(1 for c in member_count.values() if c > 1),
        "builder": "ingestion/build_commercial_bldg_artifact.py",
    }
    return artifact, meta


def write(artifact: dict, meta: dict, out: Path = OUTPUT_PATH, meta_out: Path = META_PATH) -> None:
    # mtime=0 so the same data gives the same bytes (a rebuild with no change is no diff).
    payload = (json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with open(out, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(payload)
    meta_out.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")


def main() -> None:
    artifact, meta = build()
    write(artifact, meta)
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} ({OUTPUT_PATH.stat().st_size} bytes): "
          f"{meta['units']} units ({meta['units_with_area']} with area, {meta['multi_pin10_units']} spanning more than "
          f"one PIN10), {meta['member_pins']} member PINs, Assessor {meta['assessor_year']}")


if __name__ == "__main__":
    main()
