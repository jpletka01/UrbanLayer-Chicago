"""Census tract demographics via Census Reporter API (ACS 5-year estimates)."""

import logging
import math

import httpx

from backend.config import get_settings
from backend.models import CensusTractDemographics, DistributionBucket, RentCell
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="census_tract_demographics")

TABLE_IDS = "B01001,B02001,B03003,B15003,B19001,B19013,B19301,B08301,B17001,B23025,B25077,B05002,B25064,B25003,B25002,B25031"
# The new UI's charts (Item 102): median age, units in structure, year moved in, home value, household type and size,
# moving in the last year, travel time to work. One request still: Census Reporter answers every table at once.
EXTRA_TABLE_IDS = "B01002,B25024,B25038,B25075,B11001,B25010,B07003,B08303,B08135"

# B25031 columns after the total (001), by the names ``neighborhood.rent.BEDROOM_GROUPS`` uses.
B25031_COLUMNS = {
    "no_bedroom": "B25031002", "1_bedroom": "B25031003", "2_bedrooms": "B25031004",
    "3_bedrooms": "B25031005", "4_bedrooms": "B25031006", "5_plus_bedrooms": "B25031007",
}

# Chicago (place) and Cook County geo IDs for comparison medians
CHICAGO_GEO = "16000US1714000"
COOK_COUNTY_GEO = "05000US17031"


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pct(num: object, denom: object) -> float | None:
    n = _safe_float(num)
    d = _safe_float(denom)
    if n is None or d is None or d == 0:
        return None
    return round(n / d * 100, 1)


def _dist(buckets: list[tuple[str, float]], total: float) -> list[DistributionBucket]:
    if total <= 0:
        return []
    return [
        DistributionBucket(label=label, value=round(count / total * 100, 1))
        for label, count in buckets
        if count > 0 or True  # include zero buckets for completeness
    ]


def _est(data: dict, table: str, col: str) -> float | None:
    """Extract an estimate value from the nested Census Reporter response."""
    tbl = data.get(table)
    if not tbl:
        return None
    return _safe_float(tbl.get("estimate", {}).get(col))


def _err(data: dict, table: str, col: str) -> float | None:
    """The published margin of error (90% level) for a column; None when absent, negative
    (the Census's "controlled estimate" sentinels) or not a number."""
    tbl = data.get(table)
    if not tbl:
        return None
    v = _safe_float((tbl.get("error") or {}).get(col))
    return v if v is not None and v >= 0 else None


MOE_Z = 1.645  # ACS margins of error are at the 90% confidence level


def _moe_sum(*moes: float | None) -> float | None:
    """MOE of a sum of estimates: root of the summed squares. None if any part has none."""
    if not moes or any(m is None for m in moes):
        return None
    return math.sqrt(sum(m * m for m in moes))  # type: ignore[operator]


def _moe_prop(num: float | None, num_moe: float | None, den: float | None, den_moe: float | None) -> float | None:
    """MOE (in percentage points) of a proportion whose numerator is part of its denominator,
    by the Census Bureau's formula; falls back to the ratio formula when the radicand is negative."""
    if num is None or num_moe is None or den is None or den_moe is None or den <= 0:
        return None
    p = num / den
    radicand = num_moe**2 - p**2 * den_moe**2
    if radicand < 0:
        radicand = num_moe**2 + p**2 * den_moe**2
    return round(math.sqrt(radicand) / den * 100, 1)


def _cv(estimate: float | None, moe: float | None) -> float | None:
    """Coefficient of variation: standard error (MOE / 1.645) over the estimate."""
    if estimate is None or moe is None or estimate <= 0:
        return None
    return round(moe / MOE_Z / estimate, 3)


def rent_cells(data: dict) -> dict[str, RentCell]:
    """The B25031 median gross rents by bedroom count in one geography's Census Reporter data.
    Only columns the response carries are returned; a suppressed estimate is a cell with ``estimate`` None."""
    if not data.get("B25031"):
        return {}
    cells = {}
    for name, col in B25031_COLUMNS.items():
        est = _safe_int(_est(data, "B25031", col))
        moe = _err(data, "B25031", col)
        cells[name] = RentCell(estimate=est, moe=None if moe is None else round(moe, 1),
                               cv=_cv(est, moe))
    return cells


def _parse_age(data: dict) -> tuple[list[DistributionBucket], float | None]:
    total = _est(data, "B01001", "B01001001") or 0
    # Male columns 003-025, Female columns 027-049 map to identical age ranges.
    # Combine male + female for each age group, then collapse into readable buckets.
    male_ranges = {
        "Under 5": ["B01001003"],
        "5-9": ["B01001004"],
        "10-14": ["B01001005"],
        "15-17": ["B01001006"],
        "18-19": ["B01001007"],
        "20": ["B01001008"],
        "21": ["B01001009"],
        "22-24": ["B01001010"],
        "25-29": ["B01001011"],
        "30-34": ["B01001012"],
        "35-39": ["B01001013"],
        "40-44": ["B01001014"],
        "45-49": ["B01001015"],
        "50-54": ["B01001016"],
        "55-59": ["B01001017"],
        "60-61": ["B01001018"],
        "62-64": ["B01001019"],
        "65-66": ["B01001020"],
        "67-69": ["B01001021"],
        "70-74": ["B01001022"],
        "75-79": ["B01001023"],
        "80-84": ["B01001024"],
        "85+": ["B01001025"],
    }
    # Female columns are offset by 24 (003->027, 004->028, etc.)
    age_groups: dict[str, float] = {}
    for _label, male_cols in male_ranges.items():
        for mcol in male_cols:
            male_num = int(mcol[-3:])
            female_col = f"B01001{male_num + 24:03d}"
            m = _est(data, "B01001", mcol) or 0
            f = _est(data, "B01001", female_col) or 0
            age_groups[_label] = age_groups.get(_label, 0) + m + f

    # Collapse into display buckets
    collapse = {
        "Under 18": ["Under 5", "5-9", "10-14", "15-17"],
        "18-24": ["18-19", "20", "21", "22-24"],
        "25-34": ["25-29", "30-34"],
        "35-44": ["35-39", "40-44"],
        "45-54": ["45-49", "50-54"],
        "55-64": ["55-59", "60-61", "62-64"],
        "65-74": ["65-66", "67-69", "70-74"],
        "75+": ["75-79", "80-84", "85+"],
    }
    buckets = []
    for label, keys in collapse.items():
        count = sum(age_groups.get(k, 0) for k in keys)
        buckets.append((label, count))

    return _dist(buckets, total), None


def _parse_race(data: dict) -> list[DistributionBucket]:
    total = _est(data, "B02001", "B02001001") or 0
    hispanic = _est(data, "B03003", "B03003003") or 0
    non_hispanic_total = _est(data, "B03003", "B03003002") or 0

    # Non-Hispanic race categories (scaled to non-Hispanic total)
    white = _est(data, "B02001", "B02001002") or 0
    black = _est(data, "B02001", "B02001003") or 0
    asian = _est(data, "B02001", "B02001005") or 0
    two_plus = _est(data, "B02001", "B02001008") or 0
    other = (
        (_est(data, "B02001", "B02001004") or 0)
        + (_est(data, "B02001", "B02001006") or 0)
        + (_est(data, "B02001", "B02001007") or 0)
    )

    # Scale race values to non-Hispanic proportions to avoid double-counting Hispanic
    if total > 0 and non_hispanic_total > 0:
        race_total = white + black + asian + two_plus + other
        if race_total > 0:
            factor = non_hispanic_total / race_total
            white *= factor
            black *= factor
            asian *= factor
            two_plus *= factor
            other *= factor

    buckets = [
        ("White", white),
        ("Black", black),
        ("Asian", asian),
        ("Two+", two_plus),
        ("Other", other),
        ("Hispanic", hispanic),
    ]
    return _dist(buckets, total)


def _parse_education(data: dict) -> tuple[list[DistributionBucket], float | None]:
    total = _est(data, "B15003", "B15003001") or 0

    # Collapse 25 columns into 5 readable groups
    no_degree = sum(_est(data, "B15003", f"B15003{i:03d}") or 0 for i in range(2, 17))
    hs = sum(_est(data, "B15003", f"B15003{i:03d}") or 0 for i in [17, 18])
    some_college = sum(_est(data, "B15003", f"B15003{i:03d}") or 0 for i in [19, 20, 21])
    bachelors = _est(data, "B15003", "B15003022") or 0
    graduate = sum(_est(data, "B15003", f"B15003{i:03d}") or 0 for i in [23, 24, 25])

    bachelors_plus = bachelors + graduate
    bach_pct = _pct(bachelors_plus, total)

    buckets = [
        ("No degree", no_degree),
        ("High school", hs),
        ("Some college", some_college),
        ("Bachelor's", bachelors),
        ("Graduate+", graduate),
    ]
    return _dist(buckets, total), bach_pct


def _parse_income(data: dict) -> list[DistributionBucket]:
    total = _est(data, "B19001", "B19001001") or 0

    bracket_map = {
        "Under $25K": [2, 3, 4, 5],
        "$25-50K": [6, 7, 8, 9, 10],
        "$50-75K": [11, 12],
        "$75-100K": [13],
        "$100-150K": [14, 15],
        "$150-200K": [16],
        "$200K+": [17],
    }
    buckets = []
    for label, cols in bracket_map.items():
        count = sum(_est(data, "B19001", f"B19001{c:03d}") or 0 for c in cols)
        buckets.append((label, count))

    return _dist(buckets, total)


def _parse_transportation(data: dict) -> list[DistributionBucket]:
    total = _est(data, "B08301", "B08301001") or 0

    buckets = [
        ("Drove alone", _est(data, "B08301", "B08301003") or 0),
        ("Carpooled", _est(data, "B08301", "B08301004") or 0),
        ("Public transit", _est(data, "B08301", "B08301010") or 0),
        ("Walked", _est(data, "B08301", "B08301019") or 0),
        ("Bicycle", _est(data, "B08301", "B08301018") or 0),
        ("Work from home", _est(data, "B08301", "B08301021") or 0),
        ("Other", (
            (_est(data, "B08301", "B08301016") or 0)
            + (_est(data, "B08301", "B08301017") or 0)
            + (_est(data, "B08301", "B08301020") or 0)
        )),
    ]
    return _dist(buckets, total)


def _share_buckets(data: dict, table: str, total_col: str, groups: list[tuple[str, list[str]]]) -> list[dict] | None:
    """Shares of a table's total, in percent, each with ``low`` when its margin of error is at least 10% of the share
    (Census Reporter's dagger rule). None when the table didn't answer or its total is zero."""
    total = _est(data, table, total_col)
    if not total:
        return None
    total_moe = _err(data, table, total_col)
    out = []
    for key, cols in groups:
        n = sum(_est(data, table, c) or 0 for c in cols)
        share = n / total * 100
        moe = _moe_prop(n, _moe_sum(*(_err(data, table, c) for c in cols)), total, total_moe)
        out.append({"key": key, "pct": round(share, 1), "low": bool(moe is not None and share > 0 and moe >= 0.1 * share)})
    return out


def _extras(tract: dict, city: dict, tables: dict) -> dict | None:
    """The new UI's housing, household, moving and commuting figures for the tract, with Chicago's headline figures
    beside them (the same request returns the city; whether the page shows them is the owner's call, rule 6)."""
    def cols(t: str, a: int, b: int) -> list[str]:
        return [f"{t}{i:03d}" for i in range(a, b + 1)]

    def label(t: str, col: str) -> str | None:
        return ((tables.get(t) or {}).get("columns", {}).get(col) or {}).get("name")

    def headline(d: dict) -> dict:
        workers = _est(d, "B08303", "B08303001")
        agg = _est(d, "B08135", "B08135001")
        mob_total = _est(d, "B07003", "B07003001")
        same = _est(d, "B07003", "B07003004")
        occ_total = _est(d, "B25002", "B25002001")
        vacant = _est(d, "B25002", "B25002003")
        return {
            "median_age": _est(d, "B01002", "B01002001"),
            "housing_units": _safe_int(_est(d, "B25024", "B25024001")),
            "households": _safe_int(_est(d, "B11001", "B11001001")),
            "persons_per_household": _est(d, "B25010", "B25010001"),
            "travel_minutes": round(agg / workers, 1) if agg and workers else None,
            "moved_pct": round((1 - same / mob_total) * 100, 1) if mob_total and same is not None else None,
            "occupied_pct": round((1 - vacant / occ_total) * 100, 1) if occ_total and vacant is not None else None,
            "per_capita_income": _safe_int(_est(d, "B19301", "B19301001")),
            "median_household_income": _safe_int(_est(d, "B19013", "B19013001")),
            "median_home_value": _safe_int(_est(d, "B25077", "B25077001")),
        }

    if not any(t in tract for t in ("B25024", "B11001", "B07003", "B08303")):
        return None
    # Year moved in: owners and renters together, by the release's own period names.
    moved: list[dict] | None = None
    total_hh = _est(tract, "B25038", "B25038001")
    if total_hh:
        moved = []
        for o, r in zip(range(3, 9), range(10, 16)):
            n = (_est(tract, "B25038", f"B25038{o:03d}") or 0) + (_est(tract, "B25038", f"B25038{r:03d}") or 0)
            name = (label("B25038", f"B25038{o:03d}") or "").replace("Moved in ", "")
            moe = _moe_prop(n, _moe_sum(_err(tract, "B25038", f"B25038{o:03d}"), _err(tract, "B25038", f"B25038{r:03d}")), total_hh, _err(tract, "B25038", "B25038001"))
            share = n / total_hh * 100
            moved.append({"key": name or f"col{o}", "pct": round(share, 1), "low": bool(moe is not None and share > 0 and moe >= 0.1 * share)})
        moved.reverse()  # oldest first
    return {
        "tract": headline(tract),
        "city": headline(city) if city else None,
        "structure": _share_buckets(tract, "B25024", "B25024001", [
            ("single_family", ["B25024002", "B25024003"]), ("two", ["B25024004"]), ("three_four", ["B25024005"]),
            ("five_19", ["B25024006", "B25024007"]), ("twenty_plus", ["B25024008", "B25024009"]), ("other", ["B25024010", "B25024011"]),
        ]),
        "tenure": _share_buckets(tract, "B25003", "B25003001", [("owner", ["B25003002"]), ("renter", ["B25003003"])]),
        "occupancy": _share_buckets(tract, "B25002", "B25002001", [("occupied", ["B25002002"]), ("vacant", ["B25002003"])]),
        "moved_in": moved,
        "home_value": _share_buckets(tract, "B25075", "B25075001", [
            ("under_100k", cols("B25075", 2, 14)), ("100_200k", cols("B25075", 15, 18)), ("200_300k", cols("B25075", 19, 20)),
            ("300_400k", ["B25075021"]), ("400_500k", ["B25075022"]), ("500k_1m", cols("B25075", 23, 24)), ("over_1m", cols("B25075", 25, 27)),
        ]),
        "household_type": _share_buckets(tract, "B11001", "B11001001", [
            ("married", ["B11001003"]), ("other_family", ["B11001004"]), ("alone", ["B11001008"]), ("roommates", ["B11001009"]),
        ]),
        "mobility": _share_buckets(tract, "B07003", "B07003001", [
            ("same_house", ["B07003004"]), ("same_county", ["B07003007"]), ("other_county", ["B07003010"]),
            ("other_state", ["B07003013"]), ("abroad", ["B07003016"]),
        ]),
        "travel_time": _share_buckets(tract, "B08303", "B08303001", [
            ("under_15", cols("B08303", 2, 4)), ("15_29", cols("B08303", 5, 7)), ("30_44", cols("B08303", 8, 10)),
            ("45_59", ["B08303011"]), ("60_plus", cols("B08303", 12, 13)),
        ]),
        "income": _share_buckets(tract, "B19001", "B19001001", [
            ("under_50k", cols("B19001", 2, 10)), ("50_100k", cols("B19001", 11, 13)), ("100_200k", cols("B19001", 14, 16)), ("over_200k", ["B19001017"]),
        ]),
    }


async def fetch_census_tract(
    tract_fips: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CensusTractDemographics | None:
    """Fetch tract-level ACS demographics from Census Reporter."""
    key = f"census_tract:{tract_fips}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    geo_id = f"14000US{tract_fips}"
    url = f"{settings.census_reporter_base}/data/show/latest"
    params = {
        "table_ids": f"{TABLE_IDS},{EXTRA_TABLE_IDS}",
        "geo_ids": f"{geo_id},{CHICAGO_GEO},{COOK_COUNTY_GEO}",
    }

    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    from backend.data_health import live

    try:
        if live.fault("source", "-", "census.reporter.acs"):
            raise RuntimeError("forced by DATA_HEALTH_FAULT")
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()
        live.record("census.reporter.acs", True)

        tract_data = payload.get("data", {}).get(geo_id, {})
        if not tract_data:
            log.warning("Census Reporter returned no data for tract %s", tract_fips)
            return None

        geo_meta = payload.get("geography", {}).get(geo_id, {})
        tract_name = geo_meta.get("name")

        # Parse distributions
        age_dist, _ = _parse_age(tract_data)
        education_dist, bach_pct = _parse_education(tract_data)
        income_dist = _parse_income(tract_data)
        race_dist = _parse_race(tract_data)
        transport_dist = _parse_transportation(tract_data)

        # Scalar values
        population = _safe_int(_est(tract_data, "B01001", "B01001001"))
        median_income = _safe_int(_est(tract_data, "B19013", "B19013001"))
        per_capita = _safe_int(_est(tract_data, "B19301", "B19301001"))
        home_value = _safe_int(_est(tract_data, "B25077", "B25077001"))

        median_rent = _safe_int(_est(tract_data, "B25064", "B25064001"))

        tenure_total = _est(tract_data, "B25003", "B25003001")
        owner_occ = _est(tract_data, "B25003", "B25003002")
        owner_occ_pct = _pct(owner_occ, tenure_total)

        occ_total = _est(tract_data, "B25002", "B25002001")
        vacant = _est(tract_data, "B25002", "B25002003")
        vacancy_rate = _pct(vacant, occ_total)

        poverty_total = _est(tract_data, "B17001", "B17001001")
        poverty_below = _est(tract_data, "B17001", "B17001002")
        poverty_rate = _pct(poverty_below, poverty_total)

        # Unemployed ÷ civilian labor force (B23025005 / B23025003)
        labor_force = _est(tract_data, "B23025", "B23025003")
        unemployed = _est(tract_data, "B23025", "B23025005")
        unemployment_rate = _pct(unemployed, labor_force)

        foreign_total = _est(tract_data, "B05002", "B05002013")
        native_total = _est(tract_data, "B05002", "B05002001")
        foreign_pct = _pct(foreign_total, native_total)

        # Comparison medians
        chicago_data = payload.get("data", {}).get(CHICAGO_GEO, {})
        cook_data = payload.get("data", {}).get(COOK_COUNTY_GEO, {})
        city_median = _safe_int(_est(chicago_data, "B19013", "B19013001"))
        county_median = _safe_int(_est(cook_data, "B19013", "B19013001"))

        # Margins of error (90%) and their coefficients of variation, for the figures the page shows.
        # Percentages carry their MOE in percentage points.
        bach_cols = [f"B15003{i:03d}" for i in (22, 23, 24, 25)]
        bach_moe = _moe_sum(*(_err(tract_data, "B15003", c) for c in bach_cols))
        moe: dict[str, float] = {}
        for name, value in (
            ("population", _err(tract_data, "B01001", "B01001001")),
            ("median_household_income", _err(tract_data, "B19013", "B19013001")),
            ("per_capita_income", _err(tract_data, "B19301", "B19301001")),
            ("median_home_value", _err(tract_data, "B25077", "B25077001")),
            ("median_gross_rent", _err(tract_data, "B25064", "B25064001")),
            ("owner_occupied_pct", _moe_prop(owner_occ, _err(tract_data, "B25003", "B25003002"), tenure_total, _err(tract_data, "B25003", "B25003001"))),
            ("vacancy_rate", _moe_prop(vacant, _err(tract_data, "B25002", "B25002003"), occ_total, _err(tract_data, "B25002", "B25002001"))),
            ("poverty_rate", _moe_prop(poverty_below, _err(tract_data, "B17001", "B17001002"), poverty_total, _err(tract_data, "B17001", "B17001001"))),
            ("unemployment_rate", _moe_prop(unemployed, _err(tract_data, "B23025", "B23025005"), labor_force, _err(tract_data, "B23025", "B23025003"))),
            ("bachelors_or_higher_pct", _moe_prop(
                sum(_est(tract_data, "B15003", c) or 0 for c in bach_cols), bach_moe,
                _est(tract_data, "B15003", "B15003001"), _err(tract_data, "B15003", "B15003001"))),
            ("foreign_born_pct", _moe_prop(foreign_total, _err(tract_data, "B05002", "B05002013"), native_total, _err(tract_data, "B05002", "B05002001"))),
            ("city_median_income", _err(chicago_data, "B19013", "B19013001")),
            ("county_median_income", _err(cook_data, "B19013", "B19013001")),
        ):
            if value is not None:
                moe[name] = round(value, 1)
        estimates = {
            "population": population, "median_household_income": median_income, "per_capita_income": per_capita,
            "median_home_value": home_value, "median_gross_rent": median_rent, "owner_occupied_pct": owner_occ_pct,
            "vacancy_rate": vacancy_rate, "poverty_rate": poverty_rate, "unemployment_rate": unemployment_rate,
            "bachelors_or_higher_pct": bach_pct, "foreign_born_pct": foreign_pct,
            "city_median_income": city_median, "county_median_income": county_median,
        }
        cv = {k: c for k, m in moe.items() if (c := _cv(estimates.get(k), m)) is not None}
        rent_by_bedroom = rent_cells(tract_data)
        release = payload.get("release") or {}
        years = release.get("years")
        acs_period = years.replace("-", "–") if isinstance(years, str) and years else None

        result = CensusTractDemographics(
            tract_fips=tract_fips,
            tract_name=tract_name,
            census_reporter_url=f"https://censusreporter.org/profiles/{geo_id}/",
            population=population,
            median_household_income=median_income,
            per_capita_income=per_capita,
            median_age=None,
            median_home_value=home_value,
            median_gross_rent=median_rent,
            owner_occupied_pct=owner_occ_pct,
            vacancy_rate=vacancy_rate,
            poverty_rate=poverty_rate,
            unemployment_rate=unemployment_rate,
            bachelors_or_higher_pct=bach_pct,
            foreign_born_pct=foreign_pct,
            acs_period=acs_period,
            acs_release=release.get("id") if isinstance(release.get("id"), str) else None,
            moe=moe,
            cv=cv,
            rent_by_bedroom=rent_by_bedroom,
            age_distribution=age_dist,
            income_distribution=income_dist,
            race_distribution=race_dist,
            education_distribution=education_dist,
            transportation_distribution=transport_dist,
            county_median_income=county_median,
            city_median_income=city_median,
            extras=_extras(tract_data, chicago_data, payload.get("tables") or {}),
        )
        _cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("Census Reporter fetch failed for tract %s: %s", tract_fips, exc)
        live.record("census.reporter.acs", False)
        return None
    finally:
        if owns:
            await client.aclose()
