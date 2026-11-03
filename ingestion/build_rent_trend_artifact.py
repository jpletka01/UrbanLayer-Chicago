"""Build ``rent_trend_by_area.json``: which way rents and sale prices moved, per community area (WS4 PR4).

Jack approved 2026-11-03 (plan ``plans/2026-10-30_ws4-pr4-pr5-plan.md``; decision Item 62).  Built offline and
committed, like ``rent_by_area.json``: production never calls the Census API.

* **Rent:** the community area's median gross rent in two NON-overlapping ACS 5-year periods (Census guidance:
  never compare overlapping 5-year estimates): 2015-19 on 2010 tracts and 2020-24 on 2020 tracts.  Each period
  is summed from ITS OWN vintage's tracts: 2015-19 through the City's 2010 tract -> community area table
  (``74p9-q2aq``), 2020-24 through the dominant-parcel assignment ``rent_by_area.json`` already uses.  Same
  interpolated median and Handbook margin as PR2 (``build_rent_artifact.area_rent``).  The change is
  **significant** only when it exceeds the combined 90% margin, ``|b - a| > sqrt(moe_a^2 + moe_b^2)`` (the
  Census Bureau's test for two estimates).  Nominal dollars, plus the change after inflation from the BLS
  Chicago CPI-U annual average (``CUURS23ASA0``; keyless public API).
* **Sale prices:** the median arm's-length sale price per community area, property group and year for the last
  six complete years, with n.  Assessor sales (``wvhk-k5uv``, the comps' filters: no sales under $10k, no
  excluded deed types, no multi-parcel sales) joined to the Parcel Universe's community area by PIN.  A median
  of what sold that year, NOT a price index (the mix changes year to year); a year with fewer than 30 sales is
  withheld at serve time (``provenance.confidence_state``), so the artifact keeps n.

Needs ``CENSUS_API_KEY`` in ``.env`` (read, never printed).  Writes the artifact and its ``.meta.json`` sidecar.

Usage:  PYTHONPATH=. python -m ingestion.build_rent_trend_artifact [--rent-year 2024] [--sales-end 2025]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

from eval import rent_method as rm
from ingestion.build_rent_artifact import OUTPUT_PATH as RENT_PATH, area_rent

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "rent_trend_by_area.json"
META_PATH = OUTPUT_PATH.with_name("rent_trend_by_area.meta.json")

CITY_TRACTS_2010 = "https://data.cityofchicago.org/resource/74p9-q2aq.json"
BLS_CPI = "https://api.bls.gov/publicAPI/v1/timeseries/data/"  # POST {"seriesid": ["CUURS23ASA0"], ...}
SALES = "wvhk-k5uv"
CHICAGO_TOWNSHIPS = ("70", "71", "72", "73", "74", "75", "76", "77")  # the City triad
PAGE = 50_000

# Assessor class -> the property group a sale-price trend is told for (residential classes only).
SALE_GROUPS = {
    "single_family": {"202", "203", "204", "205", "206", "207", "208", "209", "210", "234", "278", "295"},
    "two_to_six": {"211", "212"},
    "condo": {"299"},
}


def change_is_significant(a: float, moe_a: float | None, b: float, moe_b: float | None) -> bool | None:
    """The Census Bureau's test for two estimates at 90%: the difference exceeds the combined margin.
    None when a margin is missing (the change can't be judged)."""
    if moe_a is None or moe_b is None:
        return None
    return abs(b - a) > math.sqrt(moe_a ** 2 + moe_b ** 2)


def sale_group(cls: str | None) -> str | None:
    c = (cls or "").replace("-", "").strip()
    return next((g for g, codes in SALE_GROUPS.items() if c in codes), None)


def sales_medians(sales: list[tuple[str, int, float]], pin_ca: dict[str, str]) -> dict[str, dict[str, dict]]:
    """``(pin, year, price)`` sales -> ``{ca: {group: {year: {"median", "n"}}}}``; a sale is grouped by the class it
    sold as (the caller passes the group), joined to its community area by PIN10."""
    cells: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for pin_group, year, price in sales:
        pin, group = pin_group.split("|")
        ca = pin_ca.get(pin[:10])
        if ca:
            cells[(ca, group, year)].append(price)
    out: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    for (ca, group, year), prices in sorted(cells.items()):
        out[ca][group][str(year)] = {"median": round(statistics.median(prices)), "n": len(prices)}
    return {ca: dict(groups) for ca, groups in out.items()}


def _paged(client: httpx.Client, dataset: str, **params: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = rm.socrata(client, dataset, **params, **{"$limit": str(PAGE), "$offset": str(offset)})
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def _cpi_annual(client: httpx.Client, years: list[int]) -> dict[int, float]:
    resp = client.post(BLS_CPI, json={"seriesid": ["CUURS23ASA0"],
                                                        "startyear": str(min(years)), "endyear": str(max(years))})
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS CPI request failed: {body.get('message')}")
    # The keyless v1 API sends monthly values only (no M13 annual average), so the year's average is the mean of
    # its twelve months, as BLS computes it; a year missing a month is not averaged.
    months: dict[int, list[float]] = defaultdict(list)
    for row in body["Results"]["series"][0]["data"]:
        if row["period"].startswith("M") and row["period"] != "M13":
            months[int(row["year"])].append(float(row["value"]))
    out = {y: round(sum(v) / 12, 3) for y, v in months.items() if len(v) == 12}
    missing = [y for y in years if y not in out]
    if missing:
        raise RuntimeError(f"BLS CPI has no annual average for {missing}")
    return out


def build(rent_year: int, sales_end: int) -> tuple[dict, dict]:
    base_year = rent_year - 5  # the previous, non-overlapping 5-year period
    current = json.loads(RENT_PATH.read_text())
    if current["acs"]["release"] != f"acs{rent_year}_5yr":
        raise RuntimeError(f"rent_by_area.json is {current['acs']['release']}, not acs{rent_year}_5yr: rebuild it first")
    with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
        # --- rent: the earlier period on its own (2010) tracts ---
        resp = client.get(CITY_TRACTS_2010, params={"$select": "geoid10,commarea_n", "$limit": "2000"})
        resp.raise_for_status()
        tracts10 = resp.json()
        tract_ca = {r["geoid10"]: str(int(float(r["commarea_n"]))) for r in tracts10 if r.get("commarea_n")}
        geo_in = "state:17 county:031"
        rows63 = {rm._tract_geoid(r): r for r in rm.census_group(client, base_year, "B25063", "tract:*", geo_in)}
        cols = rm._bracket_columns(rm.census_labels(client, base_year, "B25063"))
        by_area: dict[str, list[dict]] = defaultdict(list)
        for tract, ca in tract_ca.items():
            if tract in rows63:
                by_area[ca].append(rows63[tract])
        earlier = {ca: area_rent(rows, cols) for ca, rows in by_area.items()}
        cpi = _cpi_annual(client, [base_year, rent_year])

        # --- sale prices: the last six complete years, joined to community areas by PIN10 ---
        pu_year = rm.socrata(client, rm.PARCEL_UNIVERSE, **{"$select": "max(year)"})[0]["max_year"]
        pins = _paged(client, rm.PARCEL_UNIVERSE, **{
            "$select": "pin10,chicago_community_area_num",
            "$where": f"year='{pu_year}' AND chicago_community_area_num IS NOT NULL",
            "$group": "pin10,chicago_community_area_num", "$order": "pin10"})
        pin_ca = {r["pin10"]: str(int(float(r["chicago_community_area_num"]))) for r in pins}
        first = sales_end - 5
        townships = ",".join(f"'{t}'" for t in CHICAGO_TOWNSHIPS)
        raw = _paged(client, SALES, **{
            "$select": "pin,year,sale_price,class",
            "$where": (f"year between '{first}' and '{sales_end}' AND township_code in ({townships})"
                       " AND sale_filter_less_than_10k = 'false' AND sale_filter_deed_type = 'false'"
                       " AND is_multisale = 'false'"),
            "$order": "row_id"})
    sales = []
    for r in raw:
        group = sale_group(r.get("class"))
        price = rm._num(r.get("sale_price"))
        if group and price and r.get("pin"):
            sales.append((f"{r['pin']}|{group}", int(float(r["year"])), price))  # some years come as "2021.0"
    by_ca_sales = sales_medians(sales, pin_ca)

    areas: dict[str, dict] = {}
    for ca in sorted(set(current["community_areas"]) | set(earlier), key=int):
        a, b = earlier.get(ca) or {}, current["community_areas"].get(ca) or {}
        rent = None
        if a.get("median") is not None and b.get("median") is not None:
            real_a = a["median"] * cpi[rent_year] / cpi[base_year]
            rent = {
                "earlier": {"median": a["median"], "moe": a.get("moe"), "households": a.get("households")},
                "later": {"median": b["median"], "moe": b.get("moe"), "households": b.get("households")},
                "change_pct": round((b["median"] - a["median"]) / a["median"] * 100, 1),
                "real_change_pct": round((b["median"] - real_a) / real_a * 100, 1),
                "significant": change_is_significant(a["median"], a.get("moe"), b["median"], b.get("moe")),
            }
        areas[ca] = {"rent": rent, "sales": by_ca_sales.get(ca, {})}

    artifact = {
        "rent": {
            "earlier": {"release": f"acs{base_year}_5yr", "period": f"{base_year - 4}–{base_year}", "tracts": "2010"},
            "later": {"release": current["acs"]["release"], "period": current["acs"]["period"], "tracts": "2020"},
            "table": "B25063", "method": "summed bracket counts, interpolated median, Handbook margin (as rent_by_area)",
            "significance": "difference > sqrt(moe_a^2 + moe_b^2) at 90%",
            "cpi": {"series": "CUURS23ASA0", "annual_average": {str(base_year): cpi[base_year], str(rent_year): cpi[rent_year]}},
        },
        "sales": {
            "years": [str(y) for y in range(first, sales_end + 1)],
            "groups": sorted(SALE_GROUPS),
            "filters": "arm's-length (no sales under $10k, no excluded deed types, no multi-parcel sales)",
            "parcel_universe_year": pu_year,
        },
        "community_areas": areas,
    }
    meta = {"built_at": date.today().isoformat(), "rent_periods": [artifact["rent"]["earlier"]["period"],
            artifact["rent"]["later"]["period"]], "sales_years": [str(first), str(sales_end)],
            "community_areas": len(areas), "sales": len(sales), "builder": "ingestion/build_rent_trend_artifact.py"}
    return artifact, meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rent-year", type=int, default=2024)
    ap.add_argument("--sales-end", type=int, default=date.today().year - 1)
    args = ap.parse_args()
    artifact, meta = build(args.rent_year, args.sales_end)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=1, sort_keys=True) + "\n")
    META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
