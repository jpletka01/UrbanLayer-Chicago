"""Chat quotas (Phase 9, decision Item 120): how many questions each visitor may ask, kept in SQLite.

  signed out   3 questions in total, counted on a signed cookie id (``anon:<id>``, period ``all``), plus a soft
               ceiling per network per day (``ip:<bucket>``, 15), so clearing cookies can't mint questions while an
               office behind one address still works
  free         50 a calendar month in Chicago (``user:<id>``, period ``YYYY-MM``)
  Pro          200 a month (a paid plan, or a voucher's ``premium_until``: ``auth`` reports both as ``premium``)
  admin        counted, never refused

A question is taken before the pipeline runs, with one atomic upsert per counter ("add 1 only while under the
limit"), and given back when the turn ends without an answer (an error, or a clarification). Limits are environment
settings (``QUOTA_*``). Nothing here stores text: subjects, periods and counts only.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request

from backend import db

CHICAGO = ZoneInfo("America/Chicago")
ANON_COOKIE = "ul_anon"
ANON_COOKIE_MAX_AGE = 365 * 86_400
# Anonymous and per-network rows older than this are pruned (they hold no identity, only counts).
ANON_RETENTION_DAYS = 90

_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def limits() -> dict[str, int]:
    """The limits in force, read from the environment each time (a change needs a restart, not a code deploy)."""
    return {
        "anonymous": int(os.environ.get("QUOTA_ANON_TOTAL", "3")),
        "anonymous_network_day": int(os.environ.get("QUOTA_ANON_IP_DAY", "15")),
        "free": int(os.environ.get("QUOTA_FREE_MONTH", "50")),
        "pro": int(os.environ.get("QUOTA_PRO_MONTH", "200")),
    }


def plan_of(user: dict | None) -> str:
    if not user:
        return "anonymous"
    tier = user.get("tier")
    if tier == "admin":
        return "admin"
    if tier == "premium":
        return "pro"
    return "free"


def month_period(now: datetime | None = None) -> str:
    now = (now or datetime.now(CHICAGO)).astimezone(CHICAGO)
    return now.strftime("%Y-%m")


def day_period(now: datetime | None = None) -> str:
    now = (now or datetime.now(CHICAGO)).astimezone(CHICAGO)
    return now.strftime("%Y-%m-%d")


def resets_on(now: datetime | None = None) -> str:
    """The first day of next month in Chicago, when a monthly allowance comes back."""
    now = (now or datetime.now(CHICAGO)).astimezone(CHICAGO)
    first = now.replace(day=1)
    return (first + timedelta(days=32)).replace(day=1).strftime("%Y-%m-%d")


# ── The anonymous id ──────────────────────────────────────────────────────────────────────────────────────────

def _secret() -> bytes:
    from backend.auth import _jwt_secret

    return hashlib.sha256(("anon-quota:" + _jwt_secret()).encode()).digest()


def sign_anon(anon_id: str) -> str:
    mac = hmac.new(_secret(), anon_id.encode(), hashlib.sha256).digest()[:16]
    return f"{anon_id}.{base64.urlsafe_b64encode(mac).decode().rstrip('=')}"


def read_anon(token: str | None) -> str | None:
    """The id in a signed cookie, or None when it's missing or its signature doesn't match."""
    if not token or "." not in token:
        return None
    anon_id, _ = token.rsplit(".", 1)
    if not anon_id or len(anon_id) > 64:
        return None
    return anon_id if hmac.compare_digest(sign_anon(anon_id), token) else None


# ── Counting ──────────────────────────────────────────────────────────────────────────────────────────────────

async def _take(subject: str, period: str, limit: int | None) -> bool:
    """Add one to a counter if it is under ``limit`` (None = no limit), in one statement. True when taken."""
    conn = db._get_db()
    now = int(time.time() * 1000)
    cur = await conn.execute(
        "INSERT INTO usage_counters (subject, period, used, updated_at) VALUES (?, ?, 1, ?) "
        "ON CONFLICT(subject, period) DO UPDATE SET used = used + 1, updated_at = excluded.updated_at "
        "WHERE usage_counters.used < ?",
        (subject, period, now, limit if limit is not None else 2**62),
    )
    taken = cur.rowcount == 1
    await conn.commit()
    return taken


async def _give_back(subject: str, period: str) -> None:
    conn = db._get_db()
    await conn.execute(
        "UPDATE usage_counters SET used = MAX(used - 1, 0), updated_at = ? WHERE subject = ? AND period = ?",
        (int(time.time() * 1000), subject, period),
    )
    await conn.commit()


async def used(subject: str, period: str) -> int:
    cur = await db._get_db().execute(
        "SELECT used FROM usage_counters WHERE subject = ? AND period = ?", (subject, period),
    )
    row = await cur.fetchone()
    return int(row[0]) if row else 0


@dataclass
class Ticket:
    """The counters one question took; ``refund`` gives them back once."""

    taken: list[tuple[str, str]] = field(default_factory=list)
    refunded: bool = False

    async def refund(self) -> None:
        if self.refunded:
            return
        self.refunded = True
        async with _get_lock():
            for subject, period in self.taken:
                await _give_back(subject, period)


class QuotaExceeded(HTTPException):
    def __init__(self, detail: dict):
        super().__init__(status_code=429, detail=detail)


def _network(request: Request) -> str:
    from backend.rate_limit import _ip_bucket, client_ip

    return _ip_bucket(client_ip(request))


async def reserve(request: Request, user: dict | None, *, now: datetime | None = None) -> tuple[Ticket, str | None]:
    """Take one question for this caller or raise ``QuotaExceeded`` (429). Returns the ticket and, for a signed-out
    visitor without a valid cookie, the new signed cookie value to set."""
    plan = plan_of(user)
    lim = limits()
    ticket = Ticket()
    try:
        db._get_db()
    except RuntimeError:
        # No database (unit tests of the chat stream): nothing to count against. Production always has one.
        return ticket, None
    async with _get_lock():
        if plan == "admin":
            subject, period = f"user:{user['id']}", month_period(now)
            await _take(subject, period, None)
            ticket.taken.append((subject, period))
            return ticket, None
        if plan in ("free", "pro"):
            subject, period, limit = f"user:{user['id']}", month_period(now), lim[plan]
            if not await _take(subject, period, limit):
                raise QuotaExceeded({"error": "quota", "plan": plan, "limit": limit, "used": limit,
                                     "resets_on": resets_on(now), "pro_limit": lim["pro"]})
            ticket.taken.append((subject, period))
            return ticket, None

        # Signed out: the cookie's id, then the network's daily ceiling.
        anon_id = read_anon(request.cookies.get(ANON_COOKIE))
        new_cookie = None
        if anon_id is None:
            anon_id = secrets.token_urlsafe(16)
            new_cookie = sign_anon(anon_id)
        anon = (f"anon:{anon_id}", "all")
        if not await _take(*anon, lim["anonymous"]):
            raise QuotaExceeded({"error": "quota", "plan": "anonymous", "limit": lim["anonymous"],
                                 "used": lim["anonymous"], "resets_on": None, "free_limit": lim["free"]})
        network = (f"ip:{_network(request)}", day_period(now))
        if not await _take(*network, lim["anonymous_network_day"]):
            await _give_back(*anon)
            raise QuotaExceeded({"error": "quota", "plan": "anonymous", "limit": lim["anonymous"],
                                 "used": await used(*anon), "resets_on": None, "network": True,
                                 "free_limit": lim["free"]})
        ticket.taken += [anon, network]
        return ticket, new_cookie


async def usage(request: Request, user: dict | None, *, now: datetime | None = None) -> dict:
    """What the page shows: the plan, questions used and allowed, and when they come back."""
    plan = plan_of(user)
    lim = limits()
    if plan == "admin":
        return {"plan": plan, "used": await used(f"user:{user['id']}", month_period(now)), "limit": None, "resets_on": None}
    if plan in ("free", "pro"):
        return {"plan": plan, "used": await used(f"user:{user['id']}", month_period(now)), "limit": lim[plan],
                "resets_on": resets_on(now), "pro_limit": lim["pro"]}
    anon_id = read_anon(request.cookies.get(ANON_COOKIE))
    n = await used(f"anon:{anon_id}", "all") if anon_id else 0
    return {"plan": plan, "used": n, "limit": lim["anonymous"], "resets_on": None, "free_limit": lim["free"]}


async def prune(now: datetime | None = None) -> int:
    """Drop anonymous and per-network rows untouched for ``ANON_RETENTION_DAYS``, and the deleted accounts' identity
    counters from past months; returns how many."""
    cutoff = int(((now or datetime.now(CHICAGO)).timestamp() - ANON_RETENTION_DAYS * 86_400) * 1000)
    conn = db._get_db()
    cur = await conn.execute(
        "DELETE FROM usage_counters WHERE ((subject LIKE 'anon:%' OR subject LIKE 'ip:%') AND updated_at < ?) "
        "OR (subject LIKE 'idh:%' AND period < ?)",
        (cutoff, month_period(now)),
    )
    await conn.commit()
    return cur.rowcount


# ── Deleting an account doesn't reset the month (Item 121) ────────────────────────────────────────────────────

def identity_subject(provider: str, subject: str) -> str:
    """A keyed hash of a sign-in identity: no email, no account id, useless without the server's secret."""
    mac = hmac.new(_secret(), f"identity:{provider}:{subject}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"idh:{mac}"


async def carry_over_on_delete(user_id: str, *, now: datetime | None = None) -> None:
    """Before an account is deleted: keep this month's count under each of its identities, so signing in again with
    the same Google/Apple/Microsoft account starts from it instead of a fresh allowance. Dropped at month end."""
    period = month_period(now)
    n = await used(f"user:{user_id}", period)
    if n <= 0:
        return
    conn = db._get_db()
    ts = int(time.time() * 1000)
    for ident in await db.list_identities(user_id):
        await conn.execute(
            "INSERT INTO usage_counters (subject, period, used, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(subject, period) DO UPDATE SET used = MAX(used, excluded.used), updated_at = excluded.updated_at",
            (identity_subject(ident["provider"], ident["subject"]), period, n, ts),
        )
    await conn.commit()


async def seed_from_identity(user_id: str, provider: str, subject: str, *, now: datetime | None = None) -> None:
    """A new account made by an identity that a deleted account used this month starts from that count."""
    period = month_period(now)
    n = await used(identity_subject(provider, subject), period)
    if n <= 0:
        return
    conn = db._get_db()
    await conn.execute(
        "INSERT INTO usage_counters (subject, period, used, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(subject, period) DO UPDATE SET used = MAX(used, excluded.used)",
        (f"user:{user_id}", period, n, int(time.time() * 1000)),
    )
    await conn.commit()
