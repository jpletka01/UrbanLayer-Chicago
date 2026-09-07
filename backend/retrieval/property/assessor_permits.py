"""Cook County Assessor permit history for a parcel.

Assessor Permits ``6yjf-dfxs`` (county portal): the permit record the ASSESSOR keeps,
keyed by 14-digit PIN. Distinct from the city permits feed already on the page
(``buildings.py``, ``ydr8-5enu``), which is address-keyed, and worth carrying for three
things the city feed does not give us:

- **PIN-keyed**, so no address matching to get wrong on a split or corner parcel.
- **A declared dollar amount** per permit.
- **An ``assessable`` flag** — the assessor's own call on whether the work is expected
  to change the assessment. A pending assessable permit is a *future tax increase*
  attached to the parcel, which is exactly the kind of fact a buyer is underwriting.

Data notes verified live 2026-09-07:
- ``pin`` is UNDASHED 14-digit here (``14313320180000``), unlike most county datasets.
- ``year`` is a float-ish string with junk in it (values of 2032 and 2027 exist, and
  ~84k rows have none), so recency is filtered on ``date_issued``, never ``year``.
- ``assessable`` is "Assessable" / "Non-Assessable" / absent (~84k).
- ``status`` is CLOSED / PENDING / OPEN / RECHECK / MANAGER REVIEW / absent.
"""

from __future__ import annotations

import datetime
import logging

import httpx

from backend.config import get_settings
from backend.models import AssessorPermit, AssessorPermitSummary
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=512, name="assessor_permits")

DATASET_ASSESSOR_PERMITS = "6yjf-dfxs"

# How far back counts as "recent activity" for a feasibility read. Older permits still
# land in `total_count`; only the returned rows and the summed amount use this window.
RECENT_YEARS = 5
MAX_ROWS = 25

# Work that has not closed out yet — the assessor may still act on it.
_LIVE_STATUSES = {"PENDING", "OPEN", "RECHECK", "MANAGER REVIEW"}


def _f(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _date(val) -> str | None:
    """Socrata floating timestamps -> YYYY-MM-DD."""
    if not val or not isinstance(val, str):
        return None
    return val.split("T", 1)[0] or None


async def get_assessor_permits(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> AssessorPermitSummary | None:
    """Assessor-side permit history for a PIN, or None when there is none on record."""
    pin_clean = pin14.replace("-", "").zfill(14)
    key = f"asr_permits:{pin_clean}"
    cached = _cache.get(key)
    if cached is not None:
        return cached or None  # falsy sentinel = known-empty

    settings = get_settings()
    cutoff = (
        datetime.date.today() - datetime.timedelta(days=365 * RECENT_YEARS)
    ).isoformat()

    try:
        rows = await socrata_get(
            DATASET_ASSESSOR_PERMITS,
            {
                "$where": f"pin='{pin_clean}' AND date_issued > '{cutoff}'",
                "$select": (
                    "date_issued,status,amount,assessable,job_code_primary,work_description"
                ),
                "$order": "date_issued DESC",
                "$limit": MAX_ROWS,
            },
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Assessor permits lookup failed for %s: %s", pin_clean, exc)
        return None

    if not rows:
        _cache.set(key, False)
        return None

    permits: list[AssessorPermit] = []
    total_amount = 0.0
    assessable_pending = False

    for r in rows:
        amount = _f(r.get("amount"))
        assessable = (r.get("assessable") or "").strip()
        status = (r.get("status") or "").strip().upper()
        if amount:
            total_amount += amount
        # The flag that matters: work the assessor calls assessable that has NOT
        # closed out. A closed assessable permit is already in the assessment.
        if assessable == "Assessable" and status in _LIVE_STATUSES:
            assessable_pending = True
        permits.append(AssessorPermit(
            date_issued=_date(r.get("date_issued")),
            status=status or None,
            amount=amount,
            assessable=(assessable == "Assessable") if assessable else None,
            job_code=(r.get("job_code_primary") or "").strip() or None,
            work_description=(r.get("work_description") or "").strip() or None,
        ))

    summary = AssessorPermitSummary(
        permits=permits,
        count=len(permits),
        truncated=len(rows) >= MAX_ROWS,
        window_years=RECENT_YEARS,
        total_declared_amount=round(total_amount, 2) if total_amount else None,
        assessable_pending=assessable_pending,
        latest_date=permits[0].date_issued if permits else None,
    )
    _cache.set(key, summary)
    return summary
