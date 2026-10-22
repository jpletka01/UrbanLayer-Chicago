"""Census tract demographics via Census Reporter API (ACS 5-year estimates)."""

import logging
import math

import httpx

from backend.config import get_settings
from backend.models import CensusTractDemographics, DistributionBucket
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="census_tract_demographics")

TABLE_IDS = "B01001,B02001,B03003,B15003,B19001,B19013,B19301,B08301,B17001,B23025,B25077,B05002,B25064,B25003,B25002"

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
        "table_ids": TABLE_IDS,
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
            age_distribution=age_dist,
            income_distribution=income_dist,
            race_distribution=race_dist,
            education_distribution=education_dist,
            transportation_distribution=transport_dist,
            county_median_income=county_median,
            city_median_income=city_median,
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
