"""Measure what new construction sells for per square foot, by community area (Deep analysis, decision Items 124, 133).

Arm's-length Assessor sales (``wvhk-k5uv``, the comps' filters) of new homes, priced per square foot of the
building's gross floor area, joined to the community area by PIN10 (Parcel Universe ``pabr-t5kh``):

* **Condos** (``3r7i-mrz4``): the unit's share of the building's gross area = ``char_building_sf`` x the unit's
  ownership share (``tieback_proration_rate``). The unit-size field (``char_unit_sf``) is filled for about 9% of
  units, too few to use. Parking spaces and common-area PINs are left out. A condo is **new on its first recorded
  sale ever, at most ``CONDO_MAX_AGE`` years after the year built** (Item 133): units first sell 0-9 years after the
  Assessor's year built (peak 4), so a 2-year window caught only the earliest few and read as a recording lag.
* **2-6 unit and single-family** (``x54s-btds``): the building's square feet. A building is **new on its first sale
  on or after the year built, within ``--max-age`` years**: most new 2-6 unit buildings stand on a lot that sold
  before the teardown, and that lot sale is not the new building's price.

The two square-foot bases differ (a condo's share of the whole building vs the residential record's building area),
so condo and 2-6 unit figures are never compared per square foot. Each group's any-age level per area is kept too.

No model calls; public Socrata reads only (a few hundred requests, ~15 min cold). Writes a JSON summary.

Usage:  PYTHONPATH=. python -m eval.new_construction_price [--first 2023 --last 2025 --max-age 2] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

from eval import rent_method as rm
from ingestion.build_rent_trend_artifact import CHICAGO_TOWNSHIPS, PAGE, SALE_GROUPS, sale_group

SALES = "wvhk-k5uv"
CONDO_CHARS = "3r7i-mrz4"
RES_CHARS = "x54s-btds"
BATCH = 250
CONDO_MAX_AGE = 5
LEVEL_GROUPS = ("condo", "two_to_six")


def _get(client: httpx.Client, dataset: str, **params: str) -> list[dict]:
    """One Socrata read, retried: the County's portal drops a long scan now and then."""
    for attempt in range(5):
        try:
            return rm.socrata(client, dataset, **params)
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == 4:
                raise
            print(f"retrying {dataset} after {exc!r}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise AssertionError


def _paged(client: httpx.Client, dataset: str, **params: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = _get(client, dataset, **params, **{"$limit": str(PAGE), "$offset": str(offset)})
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def _sqft(r: dict, condo: bool) -> float | None:
    if not condo:
        return rm._num(r.get("char_bldg_sf"))
    if r.get("is_parking_space") is True or r.get("is_common_area") is True:
        return None
    bldg, share = rm._num(r.get("char_building_sf")), rm._num(r.get("tieback_proration_rate"))
    return bldg * share if bldg and share and 0 < share < 1 else None


def _chars(client: httpx.Client, dataset: str, pins: list[str], condo: bool) -> dict[str, tuple[int, float]]:
    """PIN -> (year built, gross sq ft), the newest row."""
    cols = ("char_building_sf,tieback_proration_rate,is_parking_space,is_common_area" if condo else "char_bldg_sf")
    out: dict[str, tuple[int, float]] = {}
    seen: set[str] = set()
    for i in range(0, len(pins), BATCH):
        chunk = pins[i:i + BATCH]
        rows = _get(client, dataset, **{
            "$select": f"pin,year,char_yrblt,{cols}",
            "$where": f"pin in ({','.join(repr(p) for p in chunk)})",
            "$order": "year DESC", "$limit": "50000"})
        for r in rows:
            if r["pin"] in seen:
                continue
            seen.add(r["pin"])
            yb, sf = rm._num(r.get("char_yrblt")), _sqft(r, condo)
            if yb and sf and sf >= 300:
                out[r["pin"]] = (int(yb), sf)
    return out


def _history(client: httpx.Client, pins: list[str]) -> dict[str, list[dict]]:
    """PIN -> every recorded sale (any year, unfiltered), oldest first: to find a PIN's first sale."""
    out: dict[str, list[dict]] = defaultdict(list)
    for i in range(0, len(pins), BATCH):
        chunk = pins[i:i + BATCH]
        for r in _get(client, SALES, **{
                "$select": "pin,year,sale_date,sale_price,class,is_multisale,sale_filter_less_than_10k,"
                           "sale_filter_deed_type",
                "$where": f"pin in ({','.join(repr(p) for p in chunk)})", "$limit": "50000"}):
            out[r["pin"]].append(r)
    for rows in out.values():
        rows.sort(key=lambda r: r.get("sale_date") or "")
    return dict(out)


def _arms_length(r: dict) -> bool:
    flags = ("is_multisale", "sale_filter_less_than_10k", "sale_filter_deed_type")
    return not any(r.get(f) in (True, "true") for f in flags)


def first_new_sale(rows: list[dict], group: str, year_built: int, max_age: int) -> tuple[int, float] | None:
    """(sale year, price) of the sale that counts as new, or None.

    Condo: the unit's first recorded sale ever, if it falls within ``CONDO_MAX_AGE`` years of being built. Other
    groups: the first sale on or after the year built (an earlier sale is the lot before the teardown), within
    ``max_age`` years. Either way that sale must be arm's-length and of the same group."""
    if group == "condo":
        candidates, limit = rows[:1], CONDO_MAX_AGE
    else:
        candidates, limit = [r for r in rows if int(float(r["year"])) >= year_built][:1], max_age
    if not candidates:
        return None
    r = candidates[0]
    y = int(float(r["year"]))
    price = rm._num(r.get("sale_price"))
    if not (0 <= y - year_built <= limit) or not price or not _arms_length(r) or sale_group(r.get("class")) != group:
        return None
    return y, price


def _summary(values: list[float]) -> dict:
    values = sorted(values)
    q = statistics.quantiles(values, n=4) if len(values) >= 4 else [values[0], statistics.median(values), values[-1]]
    return {"n": len(values), "median": round(statistics.median(values)), "p25": round(q[0]), "p75": round(q[2])}


def measure(first: int, last: int, max_age: int, cache: Path | None = None) -> dict:
    townships = ",".join(f"'{t}'" for t in CHICAGO_TOWNSHIPS)
    with httpx.Client(timeout=httpx.Timeout(180.0)) as client:
        if cache and cache.exists():
            raw = json.loads(cache.read_text())
        else:
            raw = _paged(client, SALES, **{
                "$select": "pin,year,sale_price,class",
                "$where": (f"year between '{first}' and '{last}' AND township_code in ({townships})"
                           " AND sale_filter_less_than_10k = 'false' AND sale_filter_deed_type = 'false'"
                           " AND is_multisale = 'false'"),
                "$order": "row_id"})
            if cache:
                cache.write_text(json.dumps(raw))
        sales = []
        for r in raw:
            g, price = sale_group(r.get("class")), rm._num(r.get("sale_price"))
            if g and price and r.get("pin"):
                sales.append((r["pin"], g, int(float(r["year"])), price))
        print(f"{len(sales)} arm's-length residential sales {first}-{last}", file=sys.stderr)
        condo_pins = sorted({p for p, g, _, _ in sales if g == "condo"})
        other_pins = sorted({p for p, g, _, _ in sales if g != "condo"})
        chars_cache = cache.with_name(cache.stem + "_chars.json") if cache else None
        if chars_cache and chars_cache.exists():
            chars = {k: tuple(v) for k, v in json.loads(chars_cache.read_text()).items()}
        else:
            chars = _chars(client, CONDO_CHARS, condo_pins, condo=True)
            chars.update(_chars(client, RES_CHARS, other_pins, condo=False))
            if chars_cache:
                chars_cache.write_text(json.dumps(chars))
        # The PINs that could hold a new sale in the window, and every sale they ever had.
        hist_cache = cache.with_name(cache.stem + "_history.json") if cache else None
        cand = sorted({p for p, g, _, _ in sales if p in chars and g in ("condo", "two_to_six", "single_family")
                       and chars[p][0] >= first - (CONDO_MAX_AGE if g == "condo" else max_age)})
        if hist_cache and hist_cache.exists():
            history = json.loads(hist_cache.read_text())
        else:
            history = _history(client, cand)
            if hist_cache:
                hist_cache.write_text(json.dumps(history))
        group_of = {p: g for p, g, _, _ in sales}
        new = []
        for p in cand:
            hit = first_new_sale(history.get(p, []), group_of[p], chars[p][0], max_age)
            if hit and first <= hit[0] <= last:
                new.append((p, group_of[p], hit[0], hit[1]))
        print(f"{len(new)} new sales ({len(cand)} recently built PINs checked)", file=sys.stderr)
        # Every sale with a size, any age: each group's own price level per gross sq ft by area.
        level_sales = [(p, g, y, price) for p, g, y, price in sales if g in LEVEL_GROUPS and p in chars]
        pin10s = sorted({p[:10] for p, *_ in new} | {p[:10] for p, *_ in level_sales})
        area: dict[str, str] = {}
        for i in range(0, len(pin10s), BATCH):
            chunk = pin10s[i:i + BATCH]
            for g in _get(client, rm.PARCEL_UNIVERSE, **{
                    "$select": "pin10,chicago_community_area_num",
                    "$where": f"pin10 in ({','.join(repr(p) for p in chunk)}) AND chicago_community_area_num IS NOT NULL",
                    "$group": "pin10,chicago_community_area_num", "$limit": "50000"}):
                area.setdefault(g["pin10"], str(int(float(g["chicago_community_area_num"]))))

    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    city: dict[str, list[float]] = defaultdict(list)
    unit_price: dict[tuple[str, str], list[float]] = defaultdict(list)
    records: list[list] = []  # [community area, group, sale year, $/sq ft]: what the artifact builder pools
    for p, g, y, price in new:
        psf = price / chars[p][1]
        if not 50 <= psf <= 2500:  # a parking space or a data-entry slip, not a home's price per sq ft
            continue
        city[g].append(psf)
        ca = area.get(p[:10])
        if ca:
            cells[(ca, g)].append(psf)
            unit_price[(ca, g)].append(price)
            records.append([ca, g, y, round(psf, 1)])
    any_age: dict[tuple[str, str], list[float]] = defaultdict(list)
    for p, g, _, price in level_sales:
        psf = price / chars[p][1]
        ca = area.get(p[:10])
        if ca and 50 <= psf <= 2500:
            any_age[(ca, g)].append(psf)
    by_area: dict[str, dict] = defaultdict(dict)
    for (ca, g), v in any_age.items():
        by_area[ca][f"{g}_any_age"] = {"per_sqft": _summary(v)}
    for (ca, g), v in cells.items():
        by_area[ca][g] = {"per_sqft": _summary(v), "price": _summary(unit_price[(ca, g)])}
    return {
        "years": [first, last], "max_age": max_age, "condo_max_age": CONDO_MAX_AGE, "groups": sorted(SALE_GROUPS),
        "sales": len(sales), "with_chars": sum(1 for s in sales if s[0] in chars), "new": len(new),
        "city": {g: _summary(v) for g, v in city.items()},
        "community_areas": {ca: by_area[ca] for ca in sorted(by_area, key=int)},
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--first", type=int, default=2023)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--max-age", type=int, default=2)
    ap.add_argument("--out")
    ap.add_argument("--cache", type=Path, help="keep the raw sales here and reuse them on the next run")
    a = ap.parse_args()
    res = measure(a.first, a.last, a.max_age, a.cache)
    text = json.dumps(res, indent=1)
    if a.out:
        with open(a.out, "w") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
