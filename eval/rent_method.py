"""WS4 PR1 method proof: can official rent figures honestly reach Chicago community areas?

No model calls and nothing is served.  This reads public data and answers, with counts:

  A. Overall median gross rent per community area, rebuilt from tract bracket counts (B25063).
  B. Median gross rent per community area by bedroom count, rebuilt from B25068 (bedrooms x rent bracket).
  C. Median gross rent by bedroom count per census tract, as the Census publishes it (B25031).
  D. The same published medians for the Chicago PUMAs (B25031), which are unions of tracts.
  E. The Assessor's modeled apartment income (csik-bsws): coverage against ACS renter households.

Medians are not additive, so a community-area median can only come from summed bracket counts (A, B) with an
interpolated median.  The margin of error is derived two ways and both are reported: the ACS Handbook's
standard-error-of-a-median method, and a simulation from the published bracket margins of error.  A cell is
judged with the confidence standard's coefficient-of-variation rules (guides/source-confidence.md section 3).

Tract -> community area uses Parcel Universe, which carries both ids per parcel: each tract goes to the
community area holding most of its residential parcels, and the households that would be misassigned are counted.

Usage:  PYTHONPATH=. python -m eval.rent_method [--year 2024] [--out eval/results/2026-10-28/rent_method.json]
Needs CENSUS_API_KEY in .env (read, never printed).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import httpx

MOE_Z = 1.645  # ACS margins of error are at the 90% level
FADE_CV_ABOVE = 0.30  # mirrors backend/provenance.py (a test pins the agreement)
HIDE_CV_ABOVE = 0.50
HIDE_COVERAGE_BELOW = 0.10
FADE_COVERAGE_BELOW = 0.25
HIDE_N_BELOW = 30
CENSUS = "https://api.census.gov/data/{year}/acs/acs5"
SOCRATA = "https://datacatalog.cookcountyil.gov/resource/{id}.json"
PARCEL_UNIVERSE = "pabr-t5kh"
COMMERCIAL_VALUATION = "csik-bsws"
BEDROOM_GROUPS = ("no_bedroom", "1_bedroom", "2_bedrooms", "3_plus_bedrooms")
# B25031 columns after the total (001)
B25031_COLUMNS = {"002": "no_bedroom", "003": "1_bedroom", "004": "2_bedrooms", "005": "3_bedrooms", "006": "4_bedrooms",
                  "007": "5_plus_bedrooms"}


# ---------------------------------------------------------------------------------------------------------
# Pure math (unit-tested in eval/tests/test_rent_method.py)
# ---------------------------------------------------------------------------------------------------------

Bracket = tuple[float, float | None, float]  # (low edge, high edge or None when open-ended, count)

_MONEY = re.compile(r"\$([\d,]+)")


def parse_bracket(label: str) -> tuple[float, float | None] | None:
    """A Census rent-bracket label -> (low, high) with ``high`` exclusive (None = open-ended).

    "Less than $300" -> (0, 300); "$1,000 to $1,249" -> (1000, 1250); "$3,500 or more" -> (3500, None).
    Anything else (totals, "With cash rent:", "No cash rent") is not a bracket -> None."""
    nums = [int(m.replace(",", "")) for m in _MONEY.findall(label)]
    tail = label.split("!!")[-1]
    if tail.startswith("Less than") and len(nums) == 1:
        return 0.0, float(nums[0])
    if " to " in tail and len(nums) == 2:
        return float(nums[0]), float(nums[1] + 1)
    if tail.endswith("or more") and len(nums) == 1:
        return float(nums[0]), None
    return None


def bracket_percentile(brackets: list[Bracket], p: float) -> float | None:
    """Linear interpolation inside the bracket that holds the p-th share of the cumulative count.

    None when there is nothing to interpolate (no households) or the share falls in the open-ended top
    bracket, where no number can be honestly interpolated (a "$3,500 or more" median is just "3,500+")."""
    total = sum(c for _, _, c in brackets)
    if total <= 0:
        return None
    target = p * total
    cum = 0.0
    for lo, hi, count in brackets:
        if count > 0 and cum + count >= target:
            if hi is None:
                return None
            return lo + (target - cum) / count * (hi - lo)
        cum += count
    return None


def bracket_median(brackets: list[Bracket]) -> float | None:
    return bracket_percentile(brackets, 0.5)


def handbook_median_moe(brackets: list[Bracket], design_factor: float = 1.0) -> float | None:
    """The 90% margin of error of an interpolated median by the ACS General Handbook (ch. 8) method.

    SE(50%) = DF * sqrt(99/B * 50^2) percentage points, with B the weighted base; the median's 68% interval runs
    from the (50 - SE)th to the (50 + SE)th percentile; SE(median) = half that interval; MOE90 = 1.645 * SE.
    None when either percentile is unavailable (empty, or in the open-ended top bracket) or the interval
    would leave 0-100%."""
    base = sum(c for _, _, c in brackets)
    if base <= 0:
        return None
    se_p = design_factor * math.sqrt(99.0 / base * 50.0**2) / 100.0
    lo_p, hi_p = 0.5 - se_p, 0.5 + se_p
    if lo_p <= 0 or hi_p >= 1:
        return None
    lower, upper = bracket_percentile(brackets, lo_p), bracket_percentile(brackets, hi_p)
    if lower is None or upper is None:
        return None
    return MOE_Z * (upper - lower) / 2.0


def simulated_median_moe(
    edges: list[tuple[float, float | None]],
    estimates: list[list[float]],
    moes: list[list[float | None]],
    *,
    draws: int = 400,
    seed: int = 0,
) -> tuple[float | None, float | None]:
    """(median, 90% margin of error) by simulation from the published bracket margins of error.

    ``estimates[t][k]`` / ``moes[t][k]`` are tract t's count and published MOE in bracket k.  Each count is drawn
    Normal(estimate, (MOE/1.645)^2) truncated at 0, tracts are summed (independent), and the median is taken per
    draw.  Independence between brackets ignores their negative correlation; in the 2024 run the Handbook method
    nonetheless gave the wider margin (about 2x), so it is the cautious one.  (median, None) when too many draws
    land in the open-ended bracket."""
    import numpy as np

    est = np.asarray(estimates, dtype=float)
    sd = np.asarray([[0.0 if m is None or m < 0 else m / MOE_Z for m in row] for row in moes], dtype=float)
    rng = np.random.default_rng(seed)
    sample = np.clip(rng.normal(est, sd, size=(draws, *est.shape)), 0, None).sum(axis=1)  # (draws, K)
    point = bracket_median([(lo, hi, float(c)) for (lo, hi), c in zip(edges, est.sum(axis=0))])
    meds = []
    for row in sample:
        m = bracket_median([(lo, hi, float(c)) for (lo, hi), c in zip(edges, row)])
        if m is not None:
            meds.append(m)
    if point is None or len(meds) < 0.95 * draws:
        return point, None
    meds.sort()
    lo, hi = meds[int(0.05 * len(meds))], meds[min(len(meds) - 1, int(0.95 * len(meds)))]
    return point, (hi - lo) / 2.0


def judge(median: float | None, moe: float | None) -> str:
    """The confidence standard's coefficient-of-variation rule for one median.

    ``unavailable`` = no median at all (empty, or it falls in the open-ended top bracket);
    ``no_moe`` = a median but no margin we can derive (the standard calls a median without published error low)."""
    if median is None or median <= 0:
        return "unavailable"
    if moe is None:
        return "no_moe"
    cv = (moe / MOE_Z) / median
    if cv > HIDE_CV_ABOVE:
        return "withheld"
    if cv > FADE_CV_ABOVE:
        return "low"
    return "standard"


def assign_tracts(parcel_counts: dict[tuple[str, str], int]) -> dict[str, tuple[str, float]]:
    """``{(tract, community_area): residential parcels}`` -> ``{tract: (dominant community area, its share)}``."""
    by_tract: dict[str, Counter] = defaultdict(Counter)
    for (tract, area), n in parcel_counts.items():
        by_tract[tract][area] += n
    out = {}
    for tract, c in by_tract.items():
        area, n = c.most_common(1)[0]
        out[tract] = (area, n / sum(c.values()))
    return out


def judge_coverage(share: float | None) -> str:
    """Coverage rule for a partial-universe source (Assessor model vs ACS renter households)."""
    if share is None:
        return "unknown"
    if share < HIDE_COVERAGE_BELOW:
        return "withheld"
    if share < FADE_COVERAGE_BELOW:
        return "low"
    return "standard"


# ---------------------------------------------------------------------------------------------------------
# Data access (public, read-only).  The Census key is read from .env and never printed.
# ---------------------------------------------------------------------------------------------------------


def _census_key() -> str:
    from dotenv import dotenv_values

    key = dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("CENSUS_API_KEY")
    if not key:
        sys.exit("CENSUS_API_KEY is not set in .env (free key: api.census.gov/data/key_signup.html)")
    return key


def census_group(client: httpx.Client, year: int, group: str, geo_for: str, geo_in: str) -> list[dict]:
    """Every row of an ACS table group as ``{"NAME", <variable>: value, ...}`` (estimates ``E`` and margins ``M``)."""
    params = {"get": f"NAME,group({group})", "for": geo_for, "in": geo_in, "key": _census_key()}
    try:
        resp = client.get(CENSUS.format(year=year), params=params)
        resp.raise_for_status()
        rows = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        # the request URL carries the key, so never let the library's message through
        raise RuntimeError(f"Census API request for {group} {geo_for} failed ({type(exc).__name__})") from None
    head, body = rows[0], rows[1:]
    return [dict(zip(head, r, strict=True)) for r in body]


def census_labels(client: httpx.Client, year: int, group: str) -> dict[str, str]:
    data = client.get(f"{CENSUS.format(year=year)}/groups/{group}.json").json()["variables"]
    return {k: v["label"] for k, v in data.items() if k.endswith("E") and k.startswith(group)}


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if f < -999_000 else f  # the Census's -666666666 style sentinels


def socrata(client: httpx.Client, dataset: str, **params: str) -> list[dict]:
    resp = client.get(SOCRATA.format(id=dataset), params=params)
    resp.raise_for_status()
    return resp.json()


def parcel_tract_map(client: httpx.Client) -> tuple[dict[str, tuple[str, float]], dict[str, Counter], str]:
    """(tract -> (community area, share), puma -> Counter of community areas, parcel-universe year)."""
    year = socrata(client, PARCEL_UNIVERSE, **{"$select": "max(year)"})[0]["max_year"]
    where = (f"year='{year}' AND chicago_community_area_num IS NOT NULL AND census_acs5_tract_geoid IS NOT NULL"
             " AND (starts_with(class,'2') OR starts_with(class,'3'))")
    rows = socrata(client, PARCEL_UNIVERSE, **{
        "$select": "census_acs5_tract_geoid,census_acs5_puma_geoid,chicago_community_area_num,count(*)",
        "$where": where, "$group": "census_acs5_tract_geoid,census_acs5_puma_geoid,chicago_community_area_num",
        "$limit": "50000"})
    counts: dict[tuple[str, str], int] = defaultdict(int)
    pumas: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        n = int(r["count"])
        counts[(r["census_acs5_tract_geoid"], r["chicago_community_area_num"])] += n
        pumas[r["census_acs5_puma_geoid"]][r["chicago_community_area_num"]] += n
    return assign_tracts(counts), pumas, year


# ---------------------------------------------------------------------------------------------------------
# The proof
# ---------------------------------------------------------------------------------------------------------


def _tract_geoid(row: dict) -> str:
    return f"{row['state']}{row['county']}{row['tract']}"


def _bracket_columns(labels: dict[str, str], prefix_filter: str = "") -> list[tuple[str, tuple[float, float | None]]]:
    out = []
    for var, label in sorted(labels.items()):
        if prefix_filter and prefix_filter not in label:
            continue
        edges = parse_bracket(label)
        if edges is not None:
            out.append((var[:-1], edges))  # strip the trailing E -> base variable name
    return out


def _area_median(rows: list[dict], cols: list[tuple[str, tuple[float, float | None]]]) -> dict:
    """Aggregate tract rows (already limited to one community area) into one median with both margins."""
    edges = [e for _, e in cols]
    est = [[_num(r.get(f"{v}E")) or 0.0 for v, _ in cols] for r in rows]
    moe = [[_num(r.get(f"{v}M")) for v, _ in cols] for r in rows]
    summed = [sum(col) for col in zip(*est, strict=True)] if est else []
    brackets = [(lo, hi, c) for (lo, hi), c in zip(edges, summed, strict=True)]
    median = bracket_median(brackets)
    sim_median, sim_moe = (simulated_median_moe(edges, est, moe) if est and median is not None else (median, None))
    out = {"households": round(sum(summed)), "median": None if median is None else round(median),
           "top_coded": median is None and sum(summed) > 0}
    for df in (1.0, 1.5):
        m = handbook_median_moe(brackets, df)
        out[f"handbook_moe_df{df}"] = None if m is None else round(m)
        out[f"state_handbook_df{df}"] = judge(median, m)
    out["sim_moe"] = None if sim_moe is None else round(sim_moe)
    out["state_sim"] = judge(median, sim_moe)
    return out


def run(year: int, with_assessor: bool = True) -> dict:
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        tract_area, pumas, pu_year = parcel_tract_map(client)
        geo_in = "state:17 county:031"
        b25003 = {_tract_geoid(r): r for r in census_group(client, year, "B25003", "tract:*", geo_in)}
        renters = {t: _num(r.get("B25003_003E")) or 0.0 for t, r in b25003.items() if t in tract_area}
        chicago = {t: a for t, (a, _) in tract_area.items() if t in renters}

        # --- tract -> community area quality
        total_hh = sum(renters.values()) or 1.0
        spill = sum(renters[t] * (1 - tract_area[t][1]) for t in chicago)
        shares = [tract_area[t][1] for t in chicago]
        crosswalk = {
            "tracts": len(chicago), "community_areas": len(set(chicago.values())), "renter_households": round(total_hh),
            "tracts_dominant_share_below_0.90": sum(s < 0.90 for s in shares),
            "tracts_dominant_share_below_0.75": sum(s < 0.75 for s in shares),
            "spill_renter_households": round(spill), "spill_share": round(spill / total_hh, 4),
        }

        by_area: dict[str, list[str]] = defaultdict(list)
        for t, a in chicago.items():
            by_area[a].append(t)

        # --- A. overall CA median from B25063
        rows63 = {_tract_geoid(r): r for r in census_group(client, year, "B25063", "tract:*", geo_in)}
        cols63 = _bracket_columns(census_labels(client, year, "B25063"))
        overall = {a: _area_median([rows63[t] for t in ts if t in rows63], cols63) for a, ts in by_area.items()}

        # --- validity: the same aggregation over all of Chicago vs the median the Census publishes for the city
        city = _area_median([rows63[t] for t in chicago if t in rows63], cols63)
        published = census_group(client, year, "B25064", "place:14000", "state:17")[0]
        citywide_check = {"rebuilt_median": city["median"], "published_median": _num(published.get("B25064_001E")),
                          "published_moe": _num(published.get("B25064_001M")), "rebuilt_moe_handbook_df1.0": city["handbook_moe_df1.0"], "rebuilt_moe_sim": city["sim_moe"]}

        # --- B. CA x bedroom from B25068
        rows68 = {_tract_geoid(r): r for r in census_group(client, year, "B25068", "tract:*", geo_in)}
        labels68 = census_labels(client, year, "B25068")
        by_bedroom: dict[str, dict] = {g: {} for g in BEDROOM_GROUPS}
        for g, key in zip(BEDROOM_GROUPS, ("No bedroom", "1 bedroom", "2 bedrooms", "3 or more bedrooms"), strict=True):
            cols = _bracket_columns({v: lbl for v, lbl in labels68.items() if f"{key}:!!With cash rent" in lbl})
            for a, ts in by_area.items():
                by_bedroom[g][a] = _area_median([rows68[t] for t in ts if t in rows68], cols)

        # --- C. tract B25031 as published
        rows31 = census_group(client, year, "B25031", "tract:*", geo_in)
        tract_cells: dict[str, Counter] = {name: Counter() for name in B25031_COLUMNS.values()}
        for r in rows31:
            t = _tract_geoid(r)
            if t not in chicago or renters.get(t, 0) <= 0:
                continue
            for suffix, name in B25031_COLUMNS.items():
                est, moe = _num(r.get(f"B25031_{suffix}E")), _num(r.get(f"B25031_{suffix}M"))
                tract_cells[name][judge(est, moe)] += 1
        # --- D. PUMA B25031 as published
        chicago_pumas = {p for p in pumas if p and p.startswith("17")}
        rows_puma = [r for r in census_group(client, year, "B25031", "public use microdata area:*", "state:17")
                     if f"17{r['public use microdata area']}" in chicago_pumas]
        puma_cells: dict[str, Counter] = {name: Counter() for name in B25031_COLUMNS.values()}
        for r in rows_puma:
            for suffix, name in B25031_COLUMNS.items():
                est, moe = _num(r.get(f"B25031_{suffix}E")), _num(r.get(f"B25031_{suffix}M"))
                puma_cells[name][judge(est, moe)] += 1
        puma_areas = {p: dict(c.most_common(6)) for p, c in pumas.items() if p in chicago_pumas}

        # --- E. Assessor model coverage
        assessor = assessor_audit(client, renters_by_area={a: sum(renters[t] for t in ts) for a, ts in by_area.items()}) \
            if with_assessor else None

    def tally(cells: dict[str, dict], keys=("state_handbook_df1.0", "state_handbook_df1.5", "state_sim")) -> dict:
        return {k: dict(Counter(v[k] for v in cells.values())) for k in keys}

    return {
        "acs_year": year, "parcel_universe_year": pu_year, "crosswalk": crosswalk, "citywide_check": citywide_check,
        "A_overall_by_community_area": {"cells": len(overall), "states": tally(overall),
                                        "top_coded_areas": sum(v["top_coded"] for v in overall.values())},
        "B_bedroom_by_community_area": {g: {"cells": len(c), "states": tally(c),
                                            "top_coded_areas": sum(v["top_coded"] for v in c.values())}
                                        for g, c in by_bedroom.items()},
        "C_tract_published_B25031": {k: dict(v) for k, v in tract_cells.items()},
        "D_puma_published_B25031": {"pumas": len(rows_puma), "cells": {k: dict(v) for k, v in puma_cells.items()},
                                    "puma_to_community_areas": puma_areas},
        "E_assessor_model": assessor,
        "detail": {"overall": overall, "bedroom": by_bedroom},
    }


def assessor_audit(client: httpx.Client, renters_by_area: dict[str, float]) -> dict:
    """Modeled units (csik-bsws, latest year) per community area vs the ACS renter households there."""
    chicago = ("Rogers Park", "West Chicago", "Lake View", "South Chicago", "Hyde Park", "North Chicago", "Lake", "Jefferson")
    # The Assessor values a triad per year, so the newest year holds only a slice of the city (2025: 1,376 rows
    # with units vs 11,026 in the 2024 city reassessment).  Use the newest year that holds the city's multifamily stock.
    by_year = socrata(client, COMMERCIAL_VALUATION, **{
        "$select": "year,count(*)", "$where": f"tot_units>0 AND township in ({','.join(repr(t) for t in chicago)})",
        "$group": "year", "$order": "year DESC"})
    year = next(r["year"] for r in by_year if int(r["count"]) >= 5000)
    where = f"year='{year}' AND tot_units>0 AND township in ({','.join(repr(t) for t in chicago)})"
    cols = "keypin,class_es,tot_units,studiounits,_1brunits,_2brunits,_3brunits,_4brunits,pgi,egi,vacancy"
    rows, offset = [], 0
    while True:
        page = socrata(client, COMMERCIAL_VALUATION, **{"$select": cols, "$where": where, "$limit": "10000",
                                                         "$offset": str(offset), "$order": "keypin"})
        rows += page
        if len(page) < 10000:
            break
        offset += 10000
    pins = sorted({r["keypin"].replace("-", "") for r in rows})
    area_of: dict[str, str] = {}
    for i in range(0, len(pins), 400):
        chunk = pins[i:i + 400]
        got = socrata(client, PARCEL_UNIVERSE, **{
            "$select": "pin,chicago_community_area_num",
            "$where": f"pin in ({','.join(repr(p) for p in chunk)}) AND chicago_community_area_num IS NOT NULL",
            "$order": "year DESC", "$limit": "5000"})
        for g in got:
            area_of.setdefault(g["pin"], g["chicago_community_area_num"])
    per_area: dict[str, dict] = defaultdict(lambda: {"buildings": 0, "units": 0.0, "mix_complete": 0, "pgi_per_unit": []})
    unmatched = 0
    for r in rows:
        area = area_of.get(r["keypin"].replace("-", ""))
        if area is None:
            unmatched += 1
            continue
        units = _num(r.get("tot_units")) or 0.0
        mix = sum(_num(r.get(c)) or 0.0 for c in ("studiounits", "_1brunits", "_2brunits", "_3brunits", "_4brunits"))
        pgi = _num(r.get("pgi"))
        a = per_area[area]
        a["buildings"] += 1
        a["units"] += units
        a["mix_complete"] += int(abs(mix - units) < 0.5)
        if pgi and units:
            a["pgi_per_unit"].append(pgi / units / 12.0)
    out_rows = {}
    for area, a in per_area.items():
        hh = renters_by_area.get(area)
        share = None if not hh else a["units"] / hh
        pgis = a.pop("pgi_per_unit")
        out_rows[area] = {
            "buildings": a["buildings"], "modeled_units": round(a["units"]), "renter_households": None if hh is None else round(hh),
            "coverage": None if share is None else round(share, 3), "coverage_state": judge_coverage(share),
            "small_sample": a["buildings"] < HIDE_N_BELOW, "bedroom_mix_complete_share": round(a["mix_complete"] / a["buildings"], 3),
            "median_modeled_pgi_per_unit_month": None if not pgis else round(statistics.median(pgis)),
        }
    states = Counter(v["coverage_state"] for v in out_rows.values())
    return {
        "year": year, "rows_with_units_by_year": {r["year"]: int(r["count"]) for r in by_year[:4]}, "buildings": len(rows), "unmatched_to_community_area": unmatched,
        "classes": dict(Counter(r["class_es"] for r in rows).most_common(8)),
        "coverage_states": dict(states), "areas_over_100pct": sum(1 for v in out_rows.values() if (v["coverage"] or 0) > 1),
        "areas_under_30_buildings": sum(v["small_sample"] for v in out_rows.values()),
        "areas_with_no_model_rows": len(set(renters_by_area) - set(out_rows)), "by_area": out_rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--year", type=int, default=2024, help="ACS 5-year release (period ends this year)")
    ap.add_argument("--out", type=Path, help="write the full result (with per-area detail) as JSON")
    ap.add_argument("--no-assessor", action="store_true")
    args = ap.parse_args()
    result = run(args.year, with_assessor=not args.no_assessor)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    summary = {k: v for k, v in result.items() if k != "detail"}
    if summary.get("E_assessor_model"):
        summary["E_assessor_model"] = {k: v for k, v in summary["E_assessor_model"].items() if k != "by_area"}
    summary["D_puma_published_B25031"] = {k: v for k, v in summary["D_puma_published_B25031"].items() if k != "puma_to_community_areas"}
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
