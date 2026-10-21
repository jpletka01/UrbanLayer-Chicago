"""City Clerk eLMS API client: what City Council passed, and when.

WS1 owns it; the amendment disclosure, the daily legislation sync, WS6's data-health
checks and WS2 reuse it. The API is labelled BETA, takes no key and states no rate
limit, so the client:

- **never runs on the request path.** Scripts and the daily sync call it; the app reads
  their snapshot.
- **raises instead of returning ``[]``.** Every function raises
  :class:`ClerkUnavailable` when it could not check (network, 5xx, timeouts, a response
  that breaks the contract), so "nothing passed" and "couldn't check" stay distinct all
  the way to the UI. A 400 means our filter is wrong: :class:`ClerkQueryError`, never
  retried.
- **is gentle.** It makes serial requests, pauses 1 s between pages, and tries 3 times
  with 1/2/4 s backoff.

Facts the code depends on (checked against the live API 2026-10-21):

- A passed law is ``status == "90-Final"`` with ``subStatus`` in :data:`PASSED`. That
  includes ``Signed``: the 2026-06-17 omnibus building-code amendment (SO2026-0024930,
  Titles 2/14/17/18) is "Signed", not "Passed".
- Categories have subcategories ("MUNICIPAL CODE AMENDMENTS | 4-60-023 Package Goods").
  ``eq`` misses them and ``startswith``/``contains`` are rejected (400), so a category is
  matched as a string range (:func:`category_filter`).
- ``finalActionDate`` is ``T15:00Z`` (10 am Chicago) and action dates ``T05:00Z``
  (Chicago midnight). Dates are compared in America/Chicago.
- ``introductionDate`` can be months in the future (the meeting a matter is scheduled
  for), and the server rejects ``sort=recordCreateDate`` although its spec lists it, so
  the newest record is the max ``recordCreateDate`` over a filtered window.
- List rows carry ``actions``, ``attachments`` and ``relations`` as null; only
  ``/matter/{id}`` and ``/matter/recordNumber/{n}`` fill them.
- A substitute keeps its ``matterId``. ``recordNumber`` becomes ``SO…`` and
  ``originalRecordNumber`` keeps the ``O…``; the SO-named Legislation PDF is what passed.

    python -m backend.retrieval.clerk passed-since 2026-03-18 --category "MUNICIPAL CODE AMENDMENTS"
    python -m backend.retrieval.clerk title17 2026-03-18
    python -m backend.retrieval.clerk latest
    python -m backend.retrieval.clerk matter SO2026-0025391
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from collections.abc import AsyncIterator, Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.retrieval.cache import TTLCache


log = logging.getLogger(__name__)

CHICAGO = ZoneInfo("America/Chicago")
PUBLIC_MATTER_URL = "https://chicityclerkelms.chicago.gov/Matter/?matterId={id}"
USER_AGENT = "UrbanLayer/1 (+https://urbanlayerchicago.com)"

CODE_AMENDMENTS = "MUNICIPAL CODE AMENDMENTS"
ZONING_RECLASSIFICATIONS = "ZONING RECLASSIFICATIONS"
FINAL = "90-Final"
# Final outcomes that mean Council enacted the matter. Ordinances end "Passed",
# "Passed as Substitute" or "Signed"; resolutions and orders end "Adopted"/"Approved".
PASSED = frozenset({"Passed", "Passed as Substitute", "Signed", "Adopted", "Approved", "Approved as Substitute"})
# Every final subStatus seen in a year of records (2025-10-01..2026-10-21, 8,639 rows).
# Anything else is contract drift for the sync to flag, not a reason to guess.
KNOWN_FINAL_SUBSTATUSES = PASSED | {"Failed to Pass", "Placed on File", "Vetoed", "Tabled", "Published in Special Pamphlet"}

REQUIRED_FIELDS = (
    "matterId", "recordNumber", "status", "subStatus", "matterCategory", "title",
    "finalActionDate", "recordCreateDate", "lastPublicationDate",
)

PAGE_SIZE = 500
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_ATTEMPTS = 3
_BACKOFF_S = (1.0, 2.0, 4.0)
_PAGE_PAUSE_S = 1.0

_cache = TTLCache(ttl_seconds=6 * 3600, maxsize=256, name="clerk")
# (client, the event loop it was made on): a client can't outlive its loop, and scripts
# may call asyncio.run more than once.
_client: tuple[httpx.AsyncClient, asyncio.AbstractEventLoop] | None = None
_sleep = asyncio.sleep  # tests replace it so retries and page pauses don't wait


class ClerkUnavailable(Exception):
    """Couldn't check: network, 5xx, timeouts after retries, or a contract violation."""


class ClerkQueryError(Exception):
    """HTTP 400: the filter or sort we sent is invalid. Never retried."""


# --- models ---------------------------------------------------------------------------------

def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClerkUnavailable(f"unparseable date {value!r}") from exc


def chicago_date(value: datetime | None) -> date | None:
    return value.astimezone(CHICAGO).date() if value else None


class ClerkAttachment(BaseModel):
    file_name: str
    url: str
    type: str


class ClerkAction(BaseModel):
    date: datetime | None = None
    body: str = ""
    name: str = ""
    text: str = ""
    meeting_id: str = ""


class ClerkMatter(BaseModel):
    matter_id: str
    record_number: str
    original_record_number: str | None = None
    status: str
    sub_status: str
    category: str
    type: str | None = None
    title: str
    introduced_at: datetime | None = None
    final_action_at: datetime | None = None
    created_at: datetime | None = None
    last_published_at: datetime | None = None
    superseded_by: str | None = None
    relations: list[str] = Field(default_factory=list)
    attachments: list[ClerkAttachment] = Field(default_factory=list)
    actions: list[ClerkAction] = Field(default_factory=list)

    @classmethod
    def from_api(cls, row: Any) -> ClerkMatter:
        if not isinstance(row, dict):
            raise ClerkUnavailable(f"matter is not an object: {type(row).__name__}")
        missing = [k for k in REQUIRED_FIELDS if k not in row]
        if missing:
            raise ClerkUnavailable(f"matter {row.get('recordNumber')!r} lacks {missing}")
        return cls(
            matter_id=row["matterId"],
            record_number=row["recordNumber"],
            original_record_number=row.get("originalRecordNumber") or None,
            status=row["status"] or "",
            sub_status=row["subStatus"] or "",
            category=row["matterCategory"] or "",
            type=row.get("type"),
            title=(row["title"] or "").strip(),
            introduced_at=_dt(row.get("introductionDate")),
            final_action_at=_dt(row["finalActionDate"]),
            created_at=_dt(row["recordCreateDate"]),
            last_published_at=_dt(row["lastPublicationDate"]),
            superseded_by=row.get("supersededBy") or None,
            relations=[r for r in (row.get("relations") or []) if isinstance(r, str)],
            attachments=[
                ClerkAttachment(file_name=a.get("fileName") or "", url=a.get("path") or "", type=a.get("attachmentType") or "")
                for a in row.get("attachments") or [] if isinstance(a, dict)
            ],
            actions=[
                ClerkAction(
                    date=_dt(a.get("actionDate")), body=a.get("actionByName") or "", name=a.get("actionName") or "",
                    text=a.get("actionText") or "", meeting_id=a.get("meetingId") or "",
                )
                for a in row.get("actions") or [] if isinstance(a, dict)
            ],
        )

    @property
    def passed(self) -> bool:
        return self.status == FINAL and self.sub_status in PASSED

    @property
    def passed_on(self) -> date | None:
        return chicago_date(self.final_action_at) if self.passed else None

    @property
    def is_substitute(self) -> bool:
        return self.sub_status.endswith("as Substitute") or self.record_number.startswith("S")

    @property
    def url(self) -> str:
        return PUBLIC_MATTER_URL.format(id=self.matter_id)

    def legislation_pdf(self) -> ClerkAttachment | None:
        """The text that passed: for a substitute, the Legislation PDF named for the SO
        number (preferring a "Final" one); otherwise the first Legislation PDF."""
        legislation = [a for a in self.attachments if a.type == "Legislation"]
        if not legislation:
            return None
        if self.is_substitute:
            mine = [a for a in legislation if a.file_name.startswith(self.record_number)]
            final = [a for a in mine if "final" in a.file_name.lower()]
            if final or mine:
                return (final or mine)[0]
        return legislation[0]


# --- Title 17 amendments (the shape WS1's disclosure and WS6's diff both use) ---------------

_TITLE17_RE = re.compile(r"\bTitles?\b[^.;]*?\b17\b|\b17-\d+\b")
_SECTION_RE = re.compile(r"\b17-\d+(?:-\d+(?:\.\d+)?[A-Z]?(?:-[A-Z])?)?\b")
_MAP_DESIGNATION_RE = re.compile(r"^\s*(?:De-)?[Dd]esignation\b")


class Title17Amendment(BaseModel):
    record_number: str
    title: str
    passed_date: date
    url: str
    kind: str                    # "text" | "map_designation" | "omnibus"
    touched_sections: list[str]  # from the title; replaced by the reviewed list when one exists
    sections_confidence: str = "title"   # "title" | "reviewed"
    addresses: list[str] = Field(default_factory=list)  # filled by the reviewed map effects (WS1 M2/M5)


def touches_title17(title: str) -> bool:
    return bool(_TITLE17_RE.search(title))


def title17_amendment(m: ClerkMatter) -> Title17Amendment:
    if m.passed_on is None:
        raise ValueError(f"{m.record_number} has not passed")
    if _MAP_DESIGNATION_RE.search(m.title):
        kind = "map_designation"
    elif re.search(r"\bTitles\b", m.title):
        kind = "omnibus"
    else:
        kind = "text"
    sections = list(dict.fromkeys(_SECTION_RE.findall(m.title)))
    return Title17Amendment(
        record_number=m.record_number, title=m.title, passed_date=m.passed_on, url=m.url,
        kind=kind, touched_sections=sections,
    )


# --- HTTP -----------------------------------------------------------------------------------

def _get_client() -> httpx.AsyncClient:
    global _client
    loop = asyncio.get_running_loop()
    if _client is None or _client[0].is_closed or _client[1] is not loop:
        _client = (httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}), loop)
    return _client[0]


async def _get(path: str, params: dict[str, Any] | None = None, *, client: httpx.AsyncClient | None = None):
    """GET a JSON body. Returns None on 404; raises ClerkQueryError on 400."""
    client = client or _get_client()
    url = f"{get_settings().clerk_api_base}{path}"
    last: Exception | None = None
    for attempt in range(_ATTEMPTS):
        try:
            resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:  # timeouts, connection errors
            last = exc
        else:
            if resp.status_code == 400:
                raise ClerkQueryError(f"{path} {params}: {resp.text[:300]}")
            if resp.status_code == 404:
                return None
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ClerkUnavailable(f"{path}: response is not JSON") from exc
            if resp.status_code < 500:
                raise ClerkUnavailable(f"{path}: HTTP {resp.status_code}")
            last = ClerkUnavailable(f"{path}: HTTP {resp.status_code}")
        if attempt + 1 < _ATTEMPTS:
            await _sleep(_BACKOFF_S[attempt])
    raise ClerkUnavailable(f"{path}: failed after {_ATTEMPTS} attempts: {last}")


def odata_str(value: str) -> str:
    """Quote a string for a filter: 'O''Hare' style."""
    return "'" + value.replace("'", "''") + "'"


def category_filter(categories: Iterable[str]) -> str:
    """Match each category and its subcategories ("X | sub") with a string range;
    the server rejects startswith/contains."""
    parts = []
    for c in categories:
        upper = c[:-1] + chr(ord(c[-1]) + 1)
        parts.append(f"(matterCategory ge {odata_str(c)} and matterCategory lt {odata_str(upper)})")
    if not parts:
        raise ValueError("no categories")
    return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def search_matters(
    filter: str, *, top: int = PAGE_SIZE, skip: int = 0, sort: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[ClerkMatter], int]:
    """One page of /matter. Returns (matters, total count across pages)."""
    params: dict[str, Any] = {"filter": filter, "top": top, "skip": skip}
    if sort:
        params["sort"] = sort
    body = await _get("/matter", params, client=client)
    if not isinstance(body, dict) or not isinstance(body.get("data"), list) or not isinstance(body.get("meta"), dict):
        raise ClerkUnavailable("/matter: unexpected response shape")
    count = body["meta"].get("count")
    if not isinstance(count, int):
        raise ClerkUnavailable("/matter: meta.count missing")
    return [ClerkMatter.from_api(r) for r in body["data"]], count


async def iter_matters(
    filter: str, *, sort: str | None = None, max_records: int = 20_000,
    page_pause_s: float = _PAGE_PAUSE_S, client: httpx.AsyncClient | None = None,
) -> AsyncIterator[ClerkMatter]:
    """Every matter matching ``filter``, one page at a time. Raises (never truncates)
    if a page fails or comes back short."""
    skip = 0
    while True:
        matters, count = await search_matters(filter, skip=skip, sort=sort, client=client)
        if count > max_records:
            raise ClerkQueryError(f"{count} matters match; narrow the filter (max {max_records})")
        for m in matters:
            yield m
        skip += len(matters)
        if skip >= count:
            return
        if not matters:
            raise ClerkUnavailable(f"/matter: empty page at {skip} of {count}")
        await _sleep(page_pause_s)


async def get_matter(matter_id: str, *, client: httpx.AsyncClient | None = None) -> ClerkMatter | None:
    """One matter with its attachments, actions and relations; None if it doesn't exist."""
    key = f"matter:{matter_id}"
    if (hit := _cache.get(key)) is not None:
        return hit
    body = await _get(f"/matter/{matter_id}", client=client)
    if body is None:
        return None
    m = ClerkMatter.from_api(body)
    _cache.set(key, m)
    return m


async def get_matter_by_record(record_number: str, *, client: httpx.AsyncClient | None = None) -> ClerkMatter | None:
    key = f"record:{record_number}"
    if (hit := _cache.get(key)) is not None:
        return hit
    body = await _get(f"/matter/recordNumber/{record_number}", client=client)
    if body is None:
        return None
    m = ClerkMatter.from_api(body)
    _cache.set(key, m)
    return m


async def passed_since(
    day: date, categories: tuple[str, ...] = (CODE_AMENDMENTS,), *, client: httpx.AsyncClient | None = None,
) -> list[ClerkMatter]:
    """Matters in ``categories`` (subcategories included) that passed AFTER ``day``,
    comparing Chicago dates; oldest first."""
    key = f"passed:{day}:{'|'.join(categories)}"
    if (hit := _cache.get(key)) is not None:
        return hit
    out = [m for m in await final_since(day, categories, client=client) if m.passed and m.passed_on and m.passed_on > day]
    _cache.set(key, out)
    return out


async def final_since(
    day: date, categories: tuple[str, ...] = (CODE_AMENDMENTS,), *, client: httpx.AsyncClient | None = None,
) -> list[ClerkMatter]:
    """Every FINAL matter in ``categories`` acted on after ``day`` (passed or not); oldest
    first. The daily sync reads the raw outcomes to flag an unknown ``subStatus``."""
    after = datetime.combine(day + timedelta(days=1), time(0), tzinfo=CHICAGO)
    flt = f"status eq {odata_str(FINAL)} and finalActionDate ge {_utc(after)} and {category_filter(categories)}"
    out = [m async for m in iter_matters(flt, client=client)]
    out.sort(key=lambda m: (m.final_action_at or datetime.min.replace(tzinfo=timezone.utc), m.record_number))
    return out


async def passed_title17_amendments(since: date, *, client: httpx.AsyncClient | None = None) -> list[Title17Amendment]:
    """Code amendments passed after ``since`` whose title names Title 17 or a 17-x section."""
    return [title17_amendment(m) for m in await passed_since(since, (CODE_AMENDMENTS,), client=client) if touches_title17(m.title)]


async def latest_record_date(
    *, now: datetime | None = None, windows_days: tuple[int, ...] = (7, 30),
    client: httpx.AsyncClient | None = None,
) -> datetime:
    """The newest ``recordCreateDate``: a freshness signal for the Clerk's data itself.

    Filters a recent window and takes the max client-side (the server rejects sorting on
    recordCreateDate). Never introductionDate: it can be future-dated. No record in 30
    days means the feed is broken, not that Council stopped meeting.
    """
    now = now or datetime.now(timezone.utc)
    for days in windows_days:
        flt = f"recordCreateDate gt {_utc(now - timedelta(days=days))}"
        created = [m.created_at async for m in iter_matters(flt, client=client) if m.created_at]
        if created:
            return max(created)
    raise ClerkUnavailable(f"no records created in the last {windows_days[-1]} days")


# --- CLI ------------------------------------------------------------------------------------

def _row(m: ClerkMatter) -> str:
    return f"{m.passed_on or chicago_date(m.final_action_at)}  {m.record_number:<16} {m.sub_status:<22} {m.title[:110]}"


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="City Clerk eLMS API client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("passed-since", help="matters passed after DATE (Chicago date)")
    p.add_argument("date", type=date.fromisoformat)
    p.add_argument("--category", action="append", help=f"repeatable; default {CODE_AMENDMENTS!r}")
    t = sub.add_parser("title17", help="Title 17 amendments passed after DATE")
    t.add_argument("date", type=date.fromisoformat)
    sub.add_parser("latest", help="newest recordCreateDate")
    g = sub.add_parser("matter", help="one matter by record number, with attachments")
    g.add_argument("record")
    args = parser.parse_args(argv)

    if args.cmd == "passed-since":
        matters = await passed_since(args.date, tuple(args.category or (CODE_AMENDMENTS,)))
        for m in matters:
            print(_row(m))
        print(f"{len(matters)} passed after {args.date}")
    elif args.cmd == "title17":
        amendments = await passed_title17_amendments(args.date)
        for a in amendments:
            print(f"{a.passed_date}  {a.record_number:<16} {a.kind:<16} {', '.join(a.touched_sections) or '-'}")
        print(f"{len(amendments)} Title 17 amendments passed after {args.date}")
    elif args.cmd == "latest":
        print((await latest_record_date()).isoformat())
    else:
        m = await get_matter_by_record(args.record)
        if m is None:
            print(f"{args.record}: not found")
            return 1
        print(json.dumps(m.model_dump(mode="json"), indent=2))
        pdf = m.legislation_pdf()
        print(f"passed text: {pdf.file_name if pdf else 'none'}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(asyncio.run(_main(sys.argv[1:])))
