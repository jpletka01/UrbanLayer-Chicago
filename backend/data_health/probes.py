"""Probes: read a source's latest data date (and the cheap contract facts) without judging it.

Two layers. The *parsers* are pure functions over a response body, tested on recorded
fixtures. The *probes* make the (few) HTTP calls and hand the bodies to the parsers. Judging
is ``evaluate``'s job.

Every call counts toward a per-probe tally (a ``ContextVar`` set per task, bumped by an
httpx hook), so the dry run can report how many requests a source cost.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from math import cos, hypot, radians
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from backend.config import get_settings
from backend.data_health.evaluate import Finding, ProbeError, ProbeResult
from backend.data_health.registry import BY_ID, PORTAL_HOSTS, SourceSpec, sidecar_locator, socrata_locator

# No URL or parenthesised comment in the UA: the City GIS server answers 403 to a UA like
# "name/1 (+https://site)" and 200 to "name/1" (measured 2026-10-21).
USER_AGENT = "urbanlayer-data-health/1"
_TIMEOUT = httpx.Timeout(connect=8.0, read=25.0, write=10.0, pool=10.0)
CONNECT_RETRIES = 3

_tally: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar("data_health_tally", default=None)

# 121 N LaSalle St: the Census Geocoder's known answer (measured 2026-10-21: -87.63234, 41.88338).
GEOCODER_ADDRESS = "121 N LaSalle St, Chicago, IL"
GEOCODER_EXPECTED = (-87.6323, 41.8834)
GEOCODER_TOLERANCE_M = 50
# A tract in Chicago, used to read the latest ACS release off Census Reporter.
CENSUS_PROBE_GEO = "14000US17031842400"

_PTAXSIM_UPSTREAM = "https://ccao-data-public-us-east-1.s3.amazonaws.com/ptaxsim/ptaxsim-{version}.db.bz2"


# --- pure parsers (tested on fixtures) ---------------------------------------------------------

def _raise_if_error_body(body: Any, what: str) -> None:
    """A 200 with an error body is a failed read, not an empty result."""
    if isinstance(body, dict):
        if body.get("error") is True or "errorCode" in body:
            raise ProbeError("service", f"{what}: {body.get('message') or body.get('errorCode') or 'error body'}")
        err = body.get("error")
        if isinstance(err, dict):  # ArcGIS: {"error": {"code": 400, "message": ...}}
            raise ProbeError("service", f"{what}: {err.get('code')} {err.get('message') or err.get('details') or ''}".strip())


def _day(ms_or_s: float | int, ms: bool) -> date:
    return datetime.fromtimestamp(ms_or_s / (1000 if ms else 1), tz=timezone.utc).date()


def parse_socrata_view(body: Any, what: str = "view") -> tuple[date | None, tuple[str, ...]]:
    """(rowsUpdatedAt as a date, the dataset's column field names)."""
    _raise_if_error_body(body, what)
    if not isinstance(body, dict):
        raise ProbeError("service", f"{what}: unexpected body")
    ru = body.get("rowsUpdatedAt")
    published = _day(ru, ms=False) if isinstance(ru, (int, float)) else None
    return published, tuple(c.get("fieldName", "") for c in body.get("columns", []) if isinstance(c, dict))


def parse_socrata_max(body: Any, kind: str, what: str = "max") -> date | None:
    """The result of ``$select=max(col) as m``: a date, or (``max_year``) the last day of the year."""
    _raise_if_error_body(body, what)
    if not isinstance(body, list) or not body or not isinstance(body[0], dict) or body[0].get("m") in (None, ""):
        return None
    raw = str(body[0]["m"])
    if kind == "max_year":
        return date(int(float(raw)), 12, 31)
    return date.fromisoformat(raw[:10])


@dataclass(frozen=True)
class LayerInfo:
    name: str | None
    fields: tuple[str, ...]
    edited: date | None  # editingInfo.dataLastEditDate when the service reports one


def parse_arcgis_layer(body: Any, what: str = "layer") -> LayerInfo:
    _raise_if_error_body(body, what)
    if not isinstance(body, dict):
        raise ProbeError("service", f"{what}: unexpected body")
    edit = (body.get("editingInfo") or {}).get("dataLastEditDate")
    return LayerInfo(
        name=body.get("name"),
        fields=tuple(f.get("name", "") for f in body.get("fields", []) if isinstance(f, dict)),
        edited=_day(edit, ms=True) if isinstance(edit, (int, float)) else None,
    )


def parse_arcgis_count(body: Any, what: str = "count") -> int:
    _raise_if_error_body(body, what)
    if not isinstance(body, dict) or not isinstance(body.get("count"), int):
        raise ProbeError("service", f"{what}: no count in body")
    return body["count"]


def arcgis_count_params() -> dict[str, str]:
    return {"where": "1=1", "returnCountOnly": "true", "f": "json"}


def arcgis_newest_params(column: str) -> dict[str, str]:
    """The newest-edit query. Deliberately ``orderByFields`` + one row, never ``outStatistics max``:
    that returns a wrong value on this server (verified 2026-10-20)."""
    return {
        "where": "1=1", "outFields": column, "orderByFields": f"{column} DESC",
        "resultRecordCount": "1", "returnGeometry": "false", "f": "json",
    }


def parse_arcgis_newest(body: Any, column: str, what: str = "newest edit") -> date | None:
    _raise_if_error_body(body, what)
    feats = body.get("features") if isinstance(body, dict) else None
    if not feats:
        return None
    val = (feats[0].get("attributes") or {}).get(column)
    return _day(val, ms=True) if isinstance(val, (int, float)) else None


def parse_socrata_count(body: Any, what: str = "count") -> int:
    """The result of ``$select=count(*) as n``."""
    _raise_if_error_body(body, what)
    if not isinstance(body, list) or not body or not isinstance(body[0], dict) or body[0].get("n") is None:
        raise ProbeError("service", f"{what}: no count in body")
    return int(float(body[0]["n"]))


def socrata_distinct_params(field: str, where: str | None) -> dict[str, str]:
    params = {"$select": field, "$group": field, "$limit": "2000"}
    if where:
        params["$where"] = where
    return params


def parse_distinct(body: Any, field: str, what: str = "distinct") -> tuple[str, ...]:
    """Distinct values of ``field`` from a Socrata ``$group`` result or an ArcGIS ``returnDistinctValues`` one.
    A null value is left out (the contract is about the values that exist)."""
    _raise_if_error_body(body, what)
    if isinstance(body, dict) and "features" in body:
        rows = [(f.get("attributes") or {}) for f in body["features"] if isinstance(f, dict)]
    elif isinstance(body, list):
        rows = [r for r in body if isinstance(r, dict)]
    else:
        raise ProbeError("service", f"{what}: unexpected body")
    return tuple(sorted({str(r[field]) for r in rows if r.get(field) is not None}))


def arcgis_distinct_params(field: str) -> dict[str, str]:
    return {"where": "1=1", "outFields": field, "returnDistinctValues": "true", "returnGeometry": "false", "f": "json"}


def parse_census_release(body: Any) -> tuple[str, str, int]:
    """(release id, years, end year) of the newest ACS release Census Reporter serves."""
    _raise_if_error_body(body, "census release")
    rel = body.get("release") if isinstance(body, dict) else None
    if not isinstance(rel, dict) or not rel.get("years"):
        raise ProbeError("service", "census release: no release in body")
    years = str(rel["years"])
    return str(rel.get("id", "")), years, int(re.split(r"\D+", years.strip())[-1])


def parse_last_modified(headers: Any) -> date | None:
    raw = headers.get("last-modified") if headers is not None else None
    if not raw:
        return None
    return parsedate_to_datetime(raw).astimezone(timezone.utc).date()


def parse_ptaxsim_metadata(row: dict[str, Any]) -> tuple[str, date | None, int | None]:
    """(db_version, created_at date, last tax year) from the ``metadata`` table's single row."""
    version = str(row.get("db_version") or "")
    created = row.get("created_at") or row.get("created")
    return (
        version,
        date.fromisoformat(str(created)[:10]) if created else None,
        int(row["data_year_max"]) if row.get("data_year_max") is not None else None,
    )


def next_ptaxsim_version(version: str) -> str | None:
    m = re.match(r"^(\d{4})\.(\d+)\.(\d+)$", version)
    return f"{int(m.group(1)) + 1}.0.0" if m else None


def meters_between(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    k = 111_320.0
    return hypot((lon2 - lon1) * k * cos(radians((lat1 + lat2) / 2)), (lat2 - lat1) * k)


def parse_geocoder_point(body: Any) -> tuple[float, float] | None:
    matches = (body or {}).get("result", {}).get("addressMatches") if isinstance(body, dict) else None
    if not matches:
        return None
    c = matches[0].get("coordinates") or {}
    return (c["x"], c["y"]) if "x" in c and "y" in c else None


def _clean(text: str) -> str:
    """Strip query strings (they can carry API keys) from an error message."""
    return re.sub(r"\?[^\s'\"]*", "?…", str(text))[:240]


# --- the HTTP context --------------------------------------------------------------------------

@dataclass
class ProbeContext:
    client: httpx.AsyncClient
    sem: asyncio.Semaphore
    today: date
    total_requests: int = 0
    _census: asyncio.Task | None = field(default=None, repr=False)

    async def get(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        async with self.sem:
            try:
                return await self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                raise ProbeError("transient", _clean(f"{type(exc).__name__}: {exc}".rstrip(": ") or type(exc).__name__)) from exc

    async def get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, what: str = "") -> Any:
        resp = await self.get(url, params=params, headers=headers)
        if resp.status_code >= 500:
            raise ProbeError("transient", f"{what or url[:60]}: HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            raise ProbeError("service", f"{what or url[:60]}: HTTP {resp.status_code}, not JSON") from None
        if resp.status_code >= 400 and not isinstance(body, (dict, list)):
            raise ProbeError("service", f"{what}: HTTP {resp.status_code}")
        return body

    async def head(self, url: str) -> httpx.Response:
        async with self.sem:
            try:
                return await self.client.head(url)
            except httpx.HTTPError as exc:
                raise ProbeError("transient", _clean(f"{type(exc).__name__}: {exc}".rstrip(": ") or type(exc).__name__)) from exc

    def census_latest(self) -> asyncio.Task:
        """One shared read of the latest ACS release (the ACS community-area probe compares to it)."""
        if self._census is None:
            self._census = asyncio.ensure_future(_read_census_release(self))
        return self._census


def make_client(transport: httpx.AsyncBaseTransport | None = None) -> tuple[httpx.AsyncClient, Callable[[], int]]:
    """An httpx client whose every request bumps the current probe's tally (``transport``: tests)."""
    total = [0]

    async def on_request(_req: httpx.Request) -> None:
        total[0] += 1
        t = _tally.get()
        if t is not None:
            t[0] += 1

    # FEMA's hazards.fema.gov resets about half of fresh TCP connections (measured 2026-10-21: 5 of 8,
    # against 0 of 12 over one kept-alive connection), which made `fed.fema.nfhl` "fail twice in a row" on
    # production. The transport retries connection errors (never a request that got a response).
    client = httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT},
        event_hooks={"request": [on_request]}, transport=transport or httpx.AsyncHTTPTransport(retries=CONNECT_RETRIES),
    )
    return client, lambda: total[0]


# --- probes -------------------------------------------------------------------------------------

def _token(portal: str) -> dict[str, str]:
    s = get_settings()
    tok = s.socrata_app_token if portal == "city" else s.cook_county_socrata_token
    return {"X-App-Token": tok} if tok else {}


async def probe_socrata(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    portal, ds = socrata_locator(spec)
    base, headers = PORTAL_HOSTS[portal], _token(portal)
    calls = [ctx.get_json(f"{base}/api/views/{ds}.json", headers=headers, what=f"{ds} view")]
    c = spec.content
    if c is not None and c.kind in ("max_date", "max_year"):
        calls.append(ctx.get_json(
            f"{base}/resource/{ds}.json", params={"$select": f"max({c.column}) as m"}, headers=headers,
            what=f"{ds} max({c.column})",
        ))
    # M4 contract reads: a fixed-size set's row count, and the distinct values of each value-set field.
    contract = spec.contract
    band = contract is not None and contract.count_band is not None
    value_specs = contract.values if contract else ()
    extra_at = len(calls)
    if band:
        calls.append(ctx.get_json(f"{base}/resource/{ds}.json", params={"$select": "count(*) as n"}, headers=headers,
                                  what=f"{ds} count"))
    for v in value_specs:
        calls.append(ctx.get_json(f"{base}/resource/{ds}.json", params=socrata_distinct_params(v.field, v.where),
                                  headers=headers, what=f"{ds} distinct {v.field}"))
    bodies = await asyncio.gather(*calls)
    published, fields = parse_socrata_view(bodies[0], f"{ds} view")
    res = ProbeResult(published=published, fields=fields)
    i = extra_at
    if band:
        res.count = parse_socrata_count(bodies[i], f"{ds} count")
        i += 1
    for v in value_specs:
        res.values[v.field] = parse_distinct(bodies[i], v.field, f"{ds} distinct {v.field}")
        i += 1
    if c is not None and len(bodies) > 1 and c.kind in ("max_date", "max_year"):
        day = parse_socrata_max(bodies[1], c.kind, f"{ds} max({c.column})")
        if day is None:
            res.findings.append(Finding("warn", f"max({c.column}) returned no value"))
        elif c.kind == "max_year":
            res.content_year, res.content = day.year, day
        else:
            res.content = day
        if c.column and fields and c.column not in fields:
            res.findings.append(Finding("error", f"content column {c.column!r} is not in the dataset"))
        if c.reference == "census_latest_release":
            try:
                res.reference_year = (await ctx.census_latest())[2]
            except ProbeError:
                res.reference_year = None
    return res


async def probe_arcgis(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    url = spec.locator
    calls = [ctx.get_json(url, params={"f": "json"}, what="layer")]
    c = spec.content
    banded = spec.contract is not None and spec.contract.count_band is not None
    if banded:
        calls.append(ctx.get_json(f"{url}/query", params=arcgis_count_params(), what="count"))
    if c is not None and c.kind == "newest_edit":
        calls.append(ctx.get_json(f"{url}/query", params=arcgis_newest_params(c.column), what="newest edit"))
    value_specs = spec.contract.values if spec.contract else ()
    for v in value_specs:
        calls.append(ctx.get_json(f"{url}/query", params=arcgis_distinct_params(v.field), what=f"distinct {v.field}"))
    bodies = await asyncio.gather(*calls)
    info = parse_arcgis_layer(bodies[0])
    res = ProbeResult(published=info.edited, layer_name=info.name, fields=info.fields)
    i = 1
    if banded:
        res.count = parse_arcgis_count(bodies[i])
        i += 1
    if c is not None and c.kind == "newest_edit":
        res.content = parse_arcgis_newest(bodies[i], c.column)
        if res.content is None:
            res.findings.append(Finding("warn", f"no {c.column} on the newest feature"))
        i += 1
    for v in value_specs:
        body = bodies[i]
        res.values[v.field] = parse_distinct(body, v.field, f"distinct {v.field}")
        if isinstance(body, dict) and body.get("exceededTransferLimit"):
            res.findings.append(Finding("warn", f"{v.field}: more distinct values than one response holds; value set checked on a part"))
        i += 1
    return res


async def _read_census_release(ctx: ProbeContext) -> tuple[str, str, int]:
    body = await ctx.get_json(
        f"{get_settings().census_reporter_base}/data/show/latest",
        params={"table_ids": "B01003", "geo_ids": CENSUS_PROBE_GEO}, what="census release",
    )
    return parse_census_release(body)


async def probe_census_release(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    rel_id, years, end = await ctx.census_latest()
    return ProbeResult(content=date(end, 12, 31), content_year=end, info=f"latest release {rel_id} ({years})")


async def probe_census_geocoder(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    body = await ctx.get_json(
        f"{spec.locator}/locations/onelineaddress",
        params={"address": GEOCODER_ADDRESS, "benchmark": "Public_AR_Current", "format": "json"}, what="geocoder",
    )
    res = ProbeResult()
    pt = parse_geocoder_point(body)
    if pt is None:
        res.findings.append(Finding("error", f"{GEOCODER_ADDRESS} did not geocode"))
    else:
        off = meters_between(*pt, *GEOCODER_EXPECTED)
        if off > GEOCODER_TOLERANCE_M:
            res.findings.append(Finding("error", f"{GEOCODER_ADDRESS} geocodes {off:.0f} m from the expected point"))
        res.info = f"known answer within {off:.0f} m"
    return res


async def probe_fcc_area(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    body = await ctx.get_json(spec.locator, params={"lat": 41.884, "lon": -87.632, "format": "json"}, what="fcc area")
    fips = ((body or {}).get("results") or [{}])[0].get("block_fips") if isinstance(body, dict) else None
    res = ProbeResult()
    if not fips or not str(fips).startswith("17031"):
        res.findings.append(Finding("error", f"a Loop point returned block {fips!r}, expected a Cook County (17031) block"))
    else:
        res.info = f"known answer: block {fips[:11]}"
    return res


async def probe_walkscore(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    key = get_settings().walkscore_api_key
    if not key:
        return ProbeResult(skipped="no WALKSCORE_API_KEY in this environment")
    body = await ctx.get_json(spec.locator, params={
        "format": "json", "address": "121 N LaSalle St Chicago IL", "lat": 41.8834, "lon": -87.6323, "wsapikey": key,
    }, what="walkscore")
    status = body.get("status") if isinstance(body, dict) else None
    res = ProbeResult()
    if status != 1:
        res.findings.append(Finding("error", f"Walk Score status {status!r} (1 = ok; 40/41 = key rejected)"))
    return res


async def probe_gtfs_head(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    resp = await ctx.head(spec.locator)
    if resp.status_code >= 400:
        raise ProbeError("transient" if resp.status_code >= 500 else "service", f"HEAD {resp.status_code}")
    return ProbeResult(published=parse_last_modified(resp.headers))


async def probe_clerk_latest(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    from zoneinfo import ZoneInfo

    from backend.legislation.currency import clerk_source_status
    from backend.retrieval.clerk import ClerkUnavailable, latest_record_date

    try:
        latest = await latest_record_date(client=ctx.client)
    except ClerkUnavailable as exc:
        raise ProbeError("transient", _clean(str(exc))) from exc
    res = ProbeResult(content=latest.astimezone(ZoneInfo("America/Chicago")).date())
    status = clerk_source_status()
    if not status.get("contract_ok", True):
        res.findings.append(Finding("error", "the daily sync saw the Clerk's response shape change: "
                                             + "; ".join(status.get("contract_problems") or ["see the snapshot"])))
    return res


async def probe_pending_legislation(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """Freshness and last-attempt state of WS2's local, last-good snapshot."""
    from backend.config import get_settings
    from backend.legislation.pending_store import read_status

    try:
        status = read_status(get_settings().pending_legislation_path)
    except Exception as exc:  # a corrupt local artifact is a service error, not "no matters"
        raise ProbeError("service", _clean(f"{type(exc).__name__}: {exc}")) from exc
    if status is None:
        return ProbeResult(skipped="pending legislation sync has not produced a store yet")

    counts = status.counts
    res = ProbeResult(
        content=status.checked_at.date() if status.checked_at else None,
        info=(
            f"last attempt {status.latest_status}; candidates={counts.get('candidates')}, "
            f"details={counts.get('details')}, pending={counts.get('pending')}, "
            f"zoning={counts.get('zoning')}, title17={counts.get('title17')}, "
            f"placement-ready={counts.get('placement_ready')}, "
            f"placed={counts.get('placed_matters')}, unplaced={counts.get('unplaced_matters')}, "
            f"locations={counts.get('locations')}, "
            f"partial-titles={counts.get('partial_titles')}, unparsed-titles={counts.get('unparsed_titles')}, "
            f"lifecycle collapses={counts.get('lifecycle_collapses')}, "
            f"excluded non-pending={counts.get('excluded_non_pending')}, "
            f"excluded attachments={counts.get('excluded_attachments')}"
        ),
    )
    if status.latest_status == "suspect":
        problems = "; ".join(status.contract_problems) or status.last_error or "contract drift"
        res.findings.append(Finding("error", "pending snapshot contract drift: " + problems))
    elif status.latest_status == "failed":
        res.findings.append(Finding("warn", "latest pending refresh failed: " + (status.last_error or "unknown error")))
    return res


async def probe_code_text(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    from backend.legislation.currency import code_currency_status

    st = code_currency_status(datetime.combine(ctx.today, datetime.min.time(), tzinfo=timezone.utc))
    res = ProbeResult(content=date.fromisoformat(st["as_of"]) if st.get("as_of") else None)
    lag = st.get("lag") or {}
    n = lag.get("title17_passed_since")
    res.info = (f"{n} Title 17 amendments passed since, {lag.get('unreviewed')} unreviewed"
                if n is not None else "amendment count unavailable (no fresh Clerk check)")
    if st.get("check_state") == "unknown":
        res.findings.append(Finding("warn", "no fresh check of the Clerk's list of passed amendments"))
    return res


# How long a passed amendment may wait for its review (days since Council passed it). Title 17 amendments
# drive the Profile's rules, so they alarm; the others only touch sections the product cites, so they only warn.
REVIEW_WARN_DAYS = 14
REVIEW_ALARM_DAYS = 45
REVIEW_OTHER_WARN_DAYS = 45


async def probe_amendment_review(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """Is the monthly review of what Council passed being done? Reads the snapshot and the review file only.
    Its own source because ``code.municipal_text`` is acked: an alarm raised there would be swallowed."""
    from backend.legislation.currency import check_state, load_snapshot, review_backlog

    res = ProbeResult()
    if check_state(load_snapshot(), datetime.combine(ctx.today, datetime.min.time(), tzinfo=timezone.utc)) == "unknown":
        # Without a fresh Clerk check the list may be missing new amendments; chi.clerk.legislation and
        # code.municipal_text report that, so this source does not guess.
        res.info = "no fresh Clerk check, so the review backlog cannot be judged"
        return res
    backlog = review_backlog(ctx.today)
    t17, other = backlog["title17"], backlog["cited_other"]
    res.info = f"{len(t17)} Title 17 and {len(other)} other passed amendments unreviewed"
    if t17 and t17[0]["waiting_days"] > REVIEW_WARN_DAYS:
        oldest = t17[0]
        level = "alarm" if oldest["waiting_days"] > REVIEW_ALARM_DAYS else "warn"
        res.findings.append(Finding(level, (
            f"Title 17 amendment {oldest['record']} (passed {oldest['passed_on']}) has waited {oldest['waiting_days']} days "
            f"for review (warn after {REVIEW_WARN_DAYS}, alarm after {REVIEW_ALARM_DAYS}); {len(t17)} unreviewed in all")))
    if other and other[0]["waiting_days"] > REVIEW_OTHER_WARN_DAYS:
        oldest = other[0]
        res.findings.append(Finding("warn", (
            f"{oldest['record']} (passed {oldest['passed_on']}) touches a cited section and has waited "
            f"{oldest['waiting_days']} days for review (warn after {REVIEW_OTHER_WARN_DAYS}); {len(other)} unreviewed in all")))
    return res


PENDING_REVIEW_WARN_DAYS = 14
PENDING_REVIEW_ALARM_DAYS = 45
_PENDING_SNAPSHOT_MAX_AGE = timedelta(days=14)


async def probe_pending_impact_review(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """Is each pending Title 17 text proposal read and mapped? Reads the pending snapshot and the
    committed review file only. Judges nothing without a fresh snapshot (the pending-snapshot and
    Clerk sources report that), the same stance as ``internal.amendment_review``."""
    from backend.config import get_settings
    from backend.legislation import impacts
    from backend.legislation.pending_store import read_status

    res = ProbeResult()
    try:
        status = read_status(get_settings().pending_legislation_path)
        matters = impacts.read_text_matters(get_settings().pending_legislation_path) if status else []
    except Exception as exc:
        raise ProbeError("service", _clean(f"{type(exc).__name__}: {exc}")) from exc
    now = datetime.combine(ctx.today, datetime.min.time(), tzinfo=timezone.utc)
    if status is None or status.checked_at is None or now - status.checked_at.astimezone(timezone.utc) > _PENDING_SNAPSHOT_MAX_AGE:
        res.info = "no fresh pending snapshot, so the pending-amendment review backlog cannot be judged"
        return res
    reviews = impacts.load_reviews()
    waiting = impacts.backlog(matters, reviews, ctx.today)
    invalid = [
        lid for lid, review in (impacts.currency._read_json(impacts.REVIEW_FILE) or {}).get("reviews", {}).items()
        if impacts.validate_review(lid, review)
    ]
    res.info = (
        f"{len(matters)} pending Title 17 text proposals, {len(matters) - len(waiting)} reviewed, "
        f"{len(waiting)} unreviewed or outdated"
    )
    if invalid:
        res.findings.append(Finding("alarm", f"{len(invalid)} review entr{'y is' if len(invalid) == 1 else 'ies are'} invalid "
                                              f"and ignored: {', '.join(sorted(invalid)[:5])}"))
    aged = [r for r in waiting if r["waiting_days"] is not None]
    if aged and aged[0]["waiting_days"] > PENDING_REVIEW_WARN_DAYS:
        oldest = aged[0]
        level = "alarm" if oldest["waiting_days"] > PENDING_REVIEW_ALARM_DAYS else "warn"
        res.findings.append(Finding(level, (
            f"Pending Title 17 proposal {oldest['record']} ({oldest['reason']}) has waited {oldest['waiting_days']} days "
            f"since introduction for review (warn after {PENDING_REVIEW_WARN_DAYS}, alarm after {PENDING_REVIEW_ALARM_DAYS}); "
            f"{len(waiting)} unreviewed or outdated in all")))
    return res


async def probe_qdrant(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    from backend.code_vintage import get_code_vintage_record

    s = get_settings()
    record = get_code_vintage_record() or {}
    alias = s.qdrant_code_collection
    aliases, coll = await asyncio.gather(
        ctx.get_json(f"{s.qdrant_url}/aliases", what="qdrant aliases"),
        ctx.get_json(f"{s.qdrant_url}/collections/{alias}", what="qdrant collection"),
    )
    res = ProbeResult()
    target = next((a.get("collection_name") for a in (aliases.get("result") or {}).get("aliases", [])
                   if a.get("alias_name") == alias), None)
    points = ((coll.get("result") or {}) if isinstance(coll, dict) else {}).get("points_count")
    if record.get("collection") and target != record["collection"]:
        res.findings.append(Finding("alarm", f"alias {alias!r} points at {target!r}, code_vintage.json says {record['collection']!r}"))
    if record.get("chunk_count") and points != record["chunk_count"]:
        res.findings.append(Finding("alarm", f"{points} points, code_vintage.json says {record['chunk_count']}"))
    res.info = f"{alias} -> {target}, {points} points"
    return res


async def probe_zoning_cache(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    from backend.code_vintage import get_code_vintage_record

    path = get_settings().data_dir / "zoning_cache.json"
    if not path.exists():
        return ProbeResult(skipped=f"{path.name} not present here")
    meta = (json.loads(path.read_text()).get("_meta") or {})
    vintage = meta.get("code_vintage") or (meta.get("fingerprint_rebased") or {}).get("corpus")
    expected = (get_code_vintage_record() or {}).get("current_through")
    built = _day(meta["built_at"], ms=False) if isinstance(meta.get("built_at"), (int, float)) else None
    res = ProbeResult(published=built, info=f"vintage {vintage}, built {built}")
    if not vintage:
        res.findings.append(Finding("warn", "the cache records no code vintage"))
    elif expected and vintage != expected:
        res.findings.append(Finding("alarm", f"zoning cache vintage {vintage} != code text {expected}"))
    return res


async def probe_hand_table(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    from backend.code_vintage import get_code_vintage_record
    from backend.retrieval import zoning_definitions

    verified = getattr(zoning_definitions, "VERIFIED_AGAINST", None)
    expected = (get_code_vintage_record() or {}).get("current_through")
    res = ProbeResult(info=f"verified against {verified}")
    if not verified:
        res.findings.append(Finding("alarm", "zoning_definitions.VERIFIED_AGAINST is not set"))
    elif expected and verified != expected:
        res.findings.append(Finding("alarm", f"hand table verified against {verified}, code text is now {expected}: re-verify"))
    return res


async def probe_ptaxsim(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    path = get_settings().ptaxsim_db_path
    if not path.exists():
        return ProbeResult(skipped="ptaxsim.db not present here")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cur = con.execute("SELECT * FROM metadata LIMIT 1")
        row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    finally:
        con.close()
    version, created, last_year = parse_ptaxsim_metadata(row)
    res = ProbeResult(published=created, content=date(last_year, 12, 31) if last_year else None,
                      content_year=last_year, info=f"db {version}, last tax year {last_year}")
    nxt = next_ptaxsim_version(version)
    if nxt:
        resp = await ctx.head(_PTAXSIM_UPSTREAM.format(version=nxt))
        if resp.status_code == 200:
            res.findings.append(Finding("warn", f"a newer ptaxsim release is published upstream ({nxt})"))
    return res


async def probe_discovery_index(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    path = get_settings().discovery_index_path
    if not path.exists():
        return ProbeResult(skipped="discovery_index.db not present here")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT built_at, parcel_count FROM meta WHERE id = 1").fetchone()
    finally:
        con.close()
    if not row:
        return ProbeResult(skipped="discovery index has no meta row")
    return ProbeResult(content=_day(row[0], ms=False), info=f"{row[1]:,} parcels")


BACKUP_WARN_HOURS = 30    # one nightly backup missed (the check runs ~2.5 h after the 03:00 job)
BACKUP_ALARM_HOURS = 36   # a night and a half with no new backup


def parse_backup_status(body: Any, now: datetime) -> tuple[date, str, list[Finding]]:
    """(date of the newest backup, an info line, findings) from ``backup_status.json``.

    The file is written by ``scripts/backup_db.sh`` after each successful backup, so its
    ``completed_at`` going stale is how a stopped cron job (the 2026-09-28 failure) is seen.
    """
    if not isinstance(body, dict) or "completed_at" not in body:
        raise ProbeError("service", "backup_status.json has an unexpected shape")
    try:
        done = datetime.fromisoformat(str(body["completed_at"]))
    except ValueError as exc:
        raise ProbeError("service", f"backup_status.json completed_at is not a date: {exc}") from exc
    if done.tzinfo is None:
        done = done.replace(tzinfo=timezone.utc)
    hours = (now - done).total_seconds() / 3600
    size = body.get("size_bytes")
    info = f"newest backup {body.get('newest_backup', '?')}, {hours:.0f} h old, {body.get('retained', '?')} retained"
    findings: list[Finding] = []
    if hours > BACKUP_ALARM_HOURS:
        findings.append(Finding("alarm", f"the newest backup is {hours:.0f} h old (alarm after {BACKUP_ALARM_HOURS} h)"))
    elif hours > BACKUP_WARN_HOURS:
        findings.append(Finding("warn", f"the newest backup is {hours:.0f} h old (warn after {BACKUP_WARN_HOURS} h)"))
    if isinstance(size, (int, float)) and size <= 0:
        findings.append(Finding("alarm", "the newest backup is empty"))
    return done.date(), info, findings


async def probe_backup_status(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    settings = get_settings()
    path = settings.backup_status_path
    if not path.exists():
        if settings.backup_status_required:
            return ProbeResult(findings=[Finding("alarm", f"{path.name} is missing: the nightly backup has not reported "
                                                          "since it was taught to (scripts/backup_db.sh)")])
        return ProbeResult(skipped=f"{path.name} not present here (written by the host's backup job)")
    try:
        body = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProbeError("service", f"cannot read {path.name}: {exc}") from exc
    day, info, findings = parse_backup_status(body, datetime.now(timezone.utc))
    return ProbeResult(content=day, info=info, findings=findings)


async def probe_sentinels(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """Run the production zoning and overlay lookups at each key parcel and compare with the answer key
    (WS6 M4). A mismatch is an ``alarm`` finding; a parcel the lookups could not answer is a ``warn``
    (the next run asks again); no answer for any parcel is a transient probe error."""
    from backend.data_health.sentinels import load_sentinels, run_sentinels

    sentinels = load_sentinels()
    run = await run_sentinels(sentinels)
    if run.checked == 0:
        raise ProbeError("transient", "no sentinel could be checked: " + "; ".join(run.unchecked[:3]))
    res = ProbeResult(findings=list(run.findings))
    for u in run.unchecked:
        res.findings.append(Finding("warn", f"could not check {u}"))
    res.info = f"{run.green} of {len(sentinels)} sentinels match the answer key"
    return res


def parse_workflow_runs(body: Any, what: str = "workflow runs") -> tuple[date | None, str | None, str | None]:
    """``(date of the newest successful run, conclusion of the newest completed run, its URL)`` from the
    GitHub Actions ``runs`` listing. No completed run at all is ``(None, None, None)``."""
    _raise_if_error_body(body, what)
    if not isinstance(body, dict) or not isinstance(body.get("workflow_runs"), list):
        raise ProbeError("service", f"{what}: no workflow_runs in body")
    runs = [r for r in body["workflow_runs"] if isinstance(r, dict) and r.get("status") == "completed"]
    runs.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    last_ok = next((r for r in runs if r.get("conclusion") == "success"), None)
    ok_day = date.fromisoformat(str(last_ok["updated_at"])[:10]) if last_ok and last_ok.get("updated_at") else None
    newest = runs[0] if runs else None
    return ok_day, (newest or {}).get("conclusion"), (newest or {}).get("html_url")


async def probe_kit_weekly(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """Did the weekly Profile kit run, and did it pass? A failed newest run is an alarm; the age of the newest
    success feeds the usual warn/alarm days. Before the first run the workflow may not be on the default
    branch yet (404) or have no runs: that is unknown, never red."""
    resp = await ctx.get(spec.locator, params={"per_page": "10", "status": "completed"},
                         headers={"Accept": "application/vnd.github+json"})
    if resp.status_code == 404:
        return ProbeResult(info="kit-weekly.yml is not on the default branch yet")
    if resp.status_code >= 400:  # a rate limit (403/429) or a GitHub outage: ask again tomorrow, never "the kit failed"
        raise ProbeError("transient", f"GitHub Actions API: HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        raise ProbeError("service", "GitHub Actions API: not JSON") from None
    ok_day, conclusion, url = parse_workflow_runs(body)
    res = ProbeResult(content=ok_day)
    if conclusion is None:
        res.info = "no completed run yet"
    elif conclusion != "success":
        res.findings.append(Finding("alarm", f"the latest weekly kit run ended {conclusion}: {url}"))
    return res


async def probe_artifact_sidecar(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """A committed artifact dated by its ``.meta.json`` sidecar (transit stations, rent by community area); for
    transit, the CTA feed's own Last-Modified as context for "is a rebuild due"."""
    root = Path(__file__).resolve().parents[2]
    meta_path = root / sidecar_locator(spec.locator)
    try:
        meta = json.loads(meta_path.read_text())
        built = date.fromisoformat(str(meta["built_at"])[:10])
    except (OSError, ValueError, KeyError):
        return ProbeResult(findings=[Finding("warn", f"{meta_path.name} is missing or has no built_at date")])
    res = ProbeResult(content=built, info=f"built {built}")
    feed = BY_ID.get("chi.cta.gtfs") if spec.id == "artifact.transit_stations" else None
    if feed is not None:
        try:
            modified = parse_last_modified((await ctx.head(feed.locator)).headers)
        except ProbeError:
            modified = None
        if modified and modified > built:
            res.info += f"; the CTA feed was last modified {modified}"
    return res


async def probe_checker(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult:
    """The checker's own last finished run (the external dead-man is /health; this colours the panel)."""
    from backend.data_health.store import last_run_finished, open_readonly

    with open_readonly(get_settings().data_health_db_path) as con:
        finished = last_run_finished(con) if con is not None else None
    if finished is None:
        return ProbeResult(skipped="no finished run recorded yet")
    return ProbeResult(content=finished.date(), info=f"last finished run {finished:%Y-%m-%d %H:%M} UTC")


PROBES: dict[str, Callable[[SourceSpec, ProbeContext], Awaitable[ProbeResult]]] = {
    "kit_weekly": probe_kit_weekly,
    "artifact_sidecar": probe_artifact_sidecar,
    "sentinels": probe_sentinels,
    "census_release": probe_census_release,
    "census_geocoder": probe_census_geocoder,
    "fcc_area": probe_fcc_area,
    "walkscore": probe_walkscore,
    "gtfs_head": probe_gtfs_head,
    "clerk_latest": probe_clerk_latest,
    "pending_legislation": probe_pending_legislation,
    "pending_impact_review": probe_pending_impact_review,
    "code_text": probe_code_text,
    "amendment_review": probe_amendment_review,
    "qdrant": probe_qdrant,
    "zoning_cache": probe_zoning_cache,
    "hand_table": probe_hand_table,
    "ptaxsim": probe_ptaxsim,
    "discovery_index": probe_discovery_index,
    "backup_status": probe_backup_status,
    "checker": probe_checker,
}


def probe_for(spec: SourceSpec) -> Callable[[SourceSpec, ProbeContext], Awaitable[ProbeResult]] | None:
    """The probe for a source: a named one, else its kind's generic one; None if it has none yet."""
    if spec.probe == "none":
        return None
    if spec.probe:
        return PROBES[spec.probe]
    return {"socrata": probe_socrata, "arcgis_layer": probe_arcgis}.get(spec.kind)


async def run_probe(spec: SourceSpec, ctx: ProbeContext) -> ProbeResult | None:
    """Run one source's probe. A failure becomes ``ProbeResult.error``, never an exception."""
    probe = probe_for(spec)
    if probe is None:
        return None
    tally = [0]
    token = _tally.set(tally)
    started = time.monotonic()
    try:
        res = await probe(spec, ctx)
    except ProbeError as exc:
        res = ProbeResult(error=exc)
    except Exception as exc:  # a probe bug must not take the run down
        res = ProbeResult(error=ProbeError("transient", _clean(f"{type(exc).__name__}: {exc}")))
    finally:
        _tally.reset(token)
    res.requests = tally[0]
    res.latency_ms = int((time.monotonic() - started) * 1000)
    return res
