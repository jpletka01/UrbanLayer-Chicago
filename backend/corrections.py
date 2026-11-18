"""Suggest a correction (decision Item 129, PR 1): anyone may report that a lot's estimated building facts are wrong.

``POST /api/discovery/corrections`` stores one row in ``lot_corrections`` (schema v22). Nothing is applied here: a
person reviews every report later (Item 129 §4), and an accepted one only ever replaces the footprint × stories
estimate, never a government record.

Who sent it (§2):
  signed in    the account id (the row is deleted with the account)
  signed out   the signed ``ul_anon`` cookie id the question allowance uses (one is set when missing) plus a keyed
               hash of the network address (``rate_limit.client_ip``, IPv6 per /64, HMAC with the server secret);
               a raw IP is never stored or logged

Limits (§2): signed in 10 an hour and 50 open per account; signed out 3 a day per cookie and 10 a day per network
hash (Chicago days, counted in ``usage_counters``, so a deploy doesn't reset them); one open report per reporter per
lot, where a second replaces the first. Over a limit: 429 ``too_many_reports``.

What the card showed is snapshotted by the server from the Discovery index (``shown``), never taken from the client.
The only log line is the event ``correction_sent`` with the kinds and whether the reporter was signed in: never the
note, the IP, the lot or a person's id. No model calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend import db, quotas
from backend.auth import get_current_user
from backend.config import get_settings
from backend.discovery import parcel_source
from backend.rate_limit import _ip_bucket, check_saved_limit, client_ip

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

MAX_NOTE = 280
# What a client may send before the note is trimmed and capped (a bound on the request, not the stored length).
MAX_NOTE_IN = 2000
MAX_STORIES = 150

SIGNED_IN_PER_HOUR = 10
SIGNED_IN_OPEN = 50
ANON_PER_DAY = 3
NETWORK_PER_DAY = 10

TOO_MANY = {"error": "too_many_reports", "message": "Too many reports today"}

Kind = Literal["stories", "area", "gone", "condo", "other"]
_PIN = re.compile(r"^\d{10}(\d{4})?$")


class CorrectionIn(BaseModel):
    """What the form sends. Unknown fields are refused, so a client can't set a user, a status or a snapshot."""

    model_config = ConfigDict(extra="forbid")

    pin: str = Field(min_length=10, max_length=20)
    kinds: list[Kind] = Field(min_length=1, max_length=5)
    stories: int | None = Field(default=None, ge=1, le=MAX_STORIES)
    area_dir: Literal["high", "low"] | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE_IN)

    @field_validator("pin")
    @classmethod
    def _pin10(cls, v: str) -> str:
        digits = re.sub(r"[\s-]", "", v)
        if not _PIN.match(digits):
            raise ValueError("pin must be a 10- or 14-digit PIN")
        return digits[:10]

    @field_validator("kinds")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        seen: list[str] = []
        for k in v:
            if k not in seen:
                seen.append(k)
        return seen

    @field_validator("note")
    @classmethod
    def _trim(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()[:MAX_NOTE].strip()
        return v or None

    @model_validator(mode="after")
    def _consistent(self) -> "CorrectionIn":
        kinds = set(self.kinds)
        if "gone" in kinds and kinds & {"stories", "area"}:
            raise ValueError("'gone' can't be sent with 'stories' or 'area'")
        if "stories" in kinds and self.stories is None:
            raise ValueError("'stories' needs a story count")
        if "stories" not in kinds and self.stories is not None:
            raise ValueError("a story count needs the 'stories' kind")
        if "area" in kinds and self.area_dir is None:
            raise ValueError("'area' needs a direction (high or low)")
        if "area" not in kinds and self.area_dir is not None:
            raise ValueError("a direction needs the 'area' kind")
        return self


def ip_hash(request: Request) -> str:
    """A keyed hash of the caller's network (IPv6 per /64): useless without the server's secret, never reversible
    to an address. Its own key, so it can't be matched against any other keyed value we keep."""
    from backend.auth import _jwt_secret

    key = hashlib.sha256(("lot-corrections-ip:" + _jwt_secret()).encode()).digest()
    return hmac.new(key, _ip_bucket(client_ip(request)).encode(), hashlib.sha256).hexdigest()[:32]


def _shown(parcel) -> dict:
    """What the card showed for this lot, from the index the card reads (Item 129 §3)."""
    g = parcel.get
    return {
        "bldg_sqft": g("bldg_sqft"),
        "bldg_sqft_source": g("bldg_sqft_source"),
        "stories": g("stories"),
        "room_sqft": g("room_sqft"),
        # Which way a "gone" or "condo" report points: what the card said about a building and a condo (PR 4).
        "structure": g("structure"),
        "condo": g("condo"),
        "data_version": parcel_source.current_version(),
    }


def _find_lot(pin10: str):
    try:
        version = parcel_source.current_version()
    except RuntimeError:
        version = None
    parcel = parcel_source.pin10_lookup(version).get(pin10) if version else None
    if parcel is None:
        raise HTTPException(status_code=404, detail="parcel not in the index")
    return parcel


async def _signed_in_reporter(user: dict) -> str:
    # The stand-in user of local development has no users row; the table references users, so it gets one.
    from backend.saved import _owner

    return await _owner(user)


async def _open_elsewhere(uid: str, pin10: str) -> int:
    cur = await db._get_db().execute(
        "SELECT COUNT(*) FROM lot_corrections WHERE user_id = ? AND status = 'new' AND pin10 != ?", (uid, pin10),
    )
    return int((await cur.fetchone())[0])


async def _take_anon(anon_id: str, network: str) -> None:
    """Take one from the cookie's and the network's daily counts, or raise 429 (giving the first back)."""
    period = quotas.day_period()
    anon = (f"corr-anon:{anon_id}", period)
    net = (f"corr-ip:{network}", period)
    async with quotas._get_lock():
        if not await quotas._take(*anon, ANON_PER_DAY):
            raise HTTPException(status_code=429, detail=TOO_MANY)
        if not await quotas._take(*net, NETWORK_PER_DAY):
            await quotas._give_back(*anon)
            raise HTTPException(status_code=429, detail=TOO_MANY)


@router.post("/corrections", status_code=201)
async def send_correction(
    body: CorrectionIn, request: Request, response: Response, user: dict | None = Depends(get_current_user),
) -> dict:
    parcel = _find_lot(body.pin)
    conn = db._get_db()

    uid = anon_id = ip_h = None
    new_cookie = None
    if user:
        uid = await _signed_in_reporter(user)
        if await _open_elsewhere(uid, body.pin) >= SIGNED_IN_OPEN:
            raise HTTPException(status_code=429, detail=TOO_MANY)
        try:
            check_saved_limit(uid, "corrections", SIGNED_IN_PER_HOUR, window_s=3600)
        except HTTPException as exc:
            raise HTTPException(status_code=429, detail=TOO_MANY, headers=exc.headers) from None
    else:
        anon_id = quotas.read_anon(request.cookies.get(quotas.ANON_COOKIE))
        if anon_id is None:
            anon_id = secrets.token_urlsafe(16)
            new_cookie = quotas.sign_anon(anon_id)
        ip_h = ip_hash(request)
        await _take_anon(anon_id, ip_h)

    # One open report per reporter per lot: a second replaces the first.
    if uid:
        cur = await conn.execute(
            "DELETE FROM lot_corrections WHERE user_id = ? AND pin10 = ? AND status = 'new'", (uid, body.pin),
        )
    else:
        cur = await conn.execute(
            "DELETE FROM lot_corrections WHERE user_id IS NULL AND anon_id = ? AND pin10 = ? AND status = 'new'",
            (anon_id, body.pin),
        )
    replaced = cur.rowcount > 0
    cur = await conn.execute(
        "INSERT INTO lot_corrections (user_id, anon_id, ip_hash, pin10, kinds, stories, area_dir, note, shown, "
        "status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)",
        (uid, anon_id, ip_h, body.pin, json.dumps(body.kinds), body.stories, body.area_dir, body.note,
         json.dumps(_shown(parcel), separators=(",", ":")), int(time.time() * 1000)),
    )
    report_id = cur.lastrowid
    await conn.commit()

    log.info("correction_sent kinds=%s signed_in=%s", ",".join(body.kinds), bool(uid))
    if new_cookie:
        response.set_cookie(quotas.ANON_COOKIE, new_cookie, max_age=quotas.ANON_COOKIE_MAX_AGE, httponly=True,
                            secure=get_settings().auth_cookie_secure, samesite="lax")
    return {"id": report_id, "status": "new", "replaced": replaced}


# ── Review (Item 129 §4, PR 4): the admin queue and the export ───────────────────────────────────────────────────
#
# Nothing here changes a figure. Accepting a report records what it applies (`applied`); the export turns every
# accepted report into the committed file `backend/discovery/user_corrections.json`, which a person commits in a PR
# and `lot_facts` reads on the next index build (PR 5). The queue writes no file on the server.

from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from backend.auth import require_admin  # noqa: E402

admin_router = APIRouter(prefix="/api/admin/corrections", tags=["admin"])

COMMITTED_FILE = Path(__file__).resolve().parent / "discovery" / "user_corrections.json"
# Signed-out reports are deleted this long after review (Item 129 §3); signed-in ones go with the account.
ANON_RETENTION_DAYS = 180
# A reporter whose reports are rejected this often (and more often than accepted) sorts to the end, never told (§5).
MUTE_AFTER_REJECTED = 3
MAX_REASON = 200
STATUSES = ("new", "accepted", "rejected", "duplicate", "stale")


async def prune_reviewed(now_ms: int | None = None) -> int:
    """Delete signed-out reports reviewed more than 180 days ago; returns how many. An accepted one already exported
    stays in the committed file (the export merges into it, never drops an entry)."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    cutoff = now_ms - ANON_RETENTION_DAYS * 86_400_000
    conn = db._get_db()
    cur = await conn.execute(
        "DELETE FROM lot_corrections WHERE user_id IS NULL AND reviewed_at IS NOT NULL AND reviewed_at < ?", (cutoff,),
    )
    await conn.commit()
    return cur.rowcount


def _reporter(row) -> tuple[str, str]:
    return ("user", row["user_id"]) if row["user_id"] else ("anon", row["anon_id"])


def _lot_now(pin10: str) -> dict | None:
    """The lot as the index holds it today: where it is and the figures the card shows."""
    try:
        version = parcel_source.current_version()
    except RuntimeError:
        return None
    parcel = parcel_source.pin10_lookup(version).get(pin10)
    if parcel is None:
        return None
    g = parcel.get
    return {
        "address": g("address"), "lat": parcel.lat, "lon": parcel.lon, "zone_class": g("zone_class"),
        "bldg_sqft": g("bldg_sqft"), "bldg_sqft_source": g("bldg_sqft_source"), "room_sqft": g("room_sqft"),
        "structure": g("structure"), "condo": g("condo"), "data_version": version,
    }


@admin_router.get("")
async def list_corrections(status: str = "new", limit: int = 100, _admin: dict = Depends(require_admin)) -> dict:
    """One report per row for the reviewer (§4): what the card showed and shows now, what the reporter says, whether
    they were signed in and their past accepted and rejected counts, and the other open reports on the lot. Open
    reports sort signed in first, muted reporters last, oldest first. No account id, cookie id or IP hash leaves."""
    if status not in (*STATUSES, "all"):
        raise HTTPException(status_code=422, detail="unknown status")
    limit = max(1, min(limit, 500))
    pruned = await prune_reviewed()
    conn = db._get_db()
    where, args = ("", ()) if status == "all" else ("WHERE status = ?", (status,))
    cur = await conn.execute(f"SELECT * FROM lot_corrections {where} ORDER BY created_at", args)
    rows = await cur.fetchall()

    # Past verdicts per reporter, and the open reports per lot.
    cur = await conn.execute(
        "SELECT user_id, anon_id, status, COUNT(*) AS n FROM lot_corrections "
        "WHERE status IN ('accepted', 'rejected') GROUP BY user_id, anon_id, status"
    )
    history: dict[tuple[str, str], dict[str, int]] = {}
    for h in await cur.fetchall():
        history.setdefault(_reporter(h), {"accepted": 0, "rejected": 0})[h["status"]] = int(h["n"])
    cur = await conn.execute("SELECT id, pin10 FROM lot_corrections WHERE status = 'new'")
    open_by_lot: dict[str, list[int]] = {}
    for o in await cur.fetchall():
        open_by_lot.setdefault(o["pin10"], []).append(int(o["id"]))

    out = []
    for r in rows:
        past = history.get(_reporter(r), {"accepted": 0, "rejected": 0})
        if r["status"] in past:  # this report's own verdict isn't its reporter's history
            past = {**past, r["status"]: past[r["status"]] - 1}
        shown = json.loads(r["shown"]) if r["shown"] else {}
        now = _lot_now(r["pin10"])
        out.append({
            "id": r["id"], "pin10": r["pin10"], "kinds": json.loads(r["kinds"]), "stories": r["stories"],
            "area_dir": r["area_dir"], "note": r["note"], "shown": shown, "now": now,
            "changed": bool(now) and now.get("bldg_sqft") != shown.get("bldg_sqft"),
            "signed_in": r["user_id"] is not None, "past": past,
            "muted": past["rejected"] >= MUTE_AFTER_REJECTED and past["rejected"] > past["accepted"],
            "others_open": [i for i in open_by_lot.get(r["pin10"], []) if i != r["id"]],
            "status": r["status"], "created_at": r["created_at"], "reviewed_at": r["reviewed_at"],
            "review_note": r["review_note"], "applied": json.loads(r["applied"]) if r["applied"] else None,
        })
    if status == "new":
        out.sort(key=lambda x: (x["muted"], not x["signed_in"], x["created_at"]))
    else:
        out.sort(key=lambda x: x["reviewed_at"] or x["created_at"], reverse=True)
    return {"reports": out[:limit], "total": len(out), "pruned": pruned}


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["accept", "reject", "duplicate"]
    reason: str | None = Field(default=None, max_length=MAX_REASON)
    # Accepting says what to apply: the stories the reviewer sees (prefilled from the report; typed by the reviewer for
    # "floor area", since a direction alone can't make a number), no building, or nothing (a case for the Assessor).
    apply: Literal["stories", "empty", "none"] | None = None
    stories: int | None = Field(default=None, ge=1, le=MAX_STORIES)

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None

    @model_validator(mode="after")
    def _apply_rules(self) -> "ReviewIn":
        if self.action == "accept":
            if self.apply is None:
                raise ValueError("accepting needs what to apply")
            if self.apply == "stories" and self.stories is None:
                raise ValueError("applying stories needs a count")
        if (self.action != "accept" or self.apply != "stories") and self.stories is not None:
            raise ValueError("a story count goes only with applying stories")
        if self.action != "accept" and self.apply is not None:
            raise ValueError("only an accepted report applies anything")
        return self


@admin_router.post("/{report_id}/review")
async def review_correction(report_id: int, body: ReviewIn, admin: dict = Depends(require_admin)) -> dict:
    """Accept, reject or mark a duplicate. Only an open report can be reviewed (409 otherwise). Reviewing clears the
    network hash (§3: it is kept only until review)."""
    status = {"accept": "accepted", "reject": "rejected", "duplicate": "duplicate"}[body.action]
    applied = None
    if body.action == "accept":
        applied = {"stories": body.stories} if body.apply == "stories" else {"empty": True} if body.apply == "empty" else {}
    conn = db._get_db()
    cur = await conn.execute(
        "UPDATE lot_corrections SET status = ?, reviewed_by = ?, reviewed_at = ?, review_note = ?, applied = ?, "
        "ip_hash = NULL WHERE id = ? AND status = 'new'",
        (status, admin.get("id"), int(time.time() * 1000), body.reason,
         json.dumps(applied) if applied is not None else None, report_id),
    )
    await conn.commit()
    if cur.rowcount == 0:
        cur = await conn.execute("SELECT status FROM lot_corrections WHERE id = ?", (report_id,))
        row = await cur.fetchone()
        raise HTTPException(status_code=404 if row is None else 409,
                            detail="no such report" if row is None else f"already {row['status']}")
    log.info("correction_reviewed action=%s", body.action)
    return {"id": report_id, "status": status, "applied": applied}


def _read_committed() -> dict:
    try:
        return json.loads(COMMITTED_FILE.read_text())
    except FileNotFoundError:
        return {}


def _dump(entries: dict) -> str:
    return json.dumps(dict(sorted(entries.items())), indent=2, sort_keys=True) + "\n"


@admin_router.get("/export")
async def export_corrections(_admin: dict = Depends(require_admin)) -> dict:
    """`backend/discovery/user_corrections.json` with every accepted report that applies something, merged into the
    committed copy (an entry is never dropped here: removing one is a hand edit in its own PR), plus a unified diff
    against it, ready for a PR. One entry per PIN10: the latest reviewed report's figure, every accepted report's id.
    Nothing is written on the server."""
    import difflib

    committed = _read_committed()
    entries = {k: dict(v) for k, v in committed.items()}
    cur = await db._get_db().execute(
        "SELECT id, pin10, applied, reviewed_at, review_note, kinds FROM lot_corrections "
        "WHERE status = 'accepted' AND applied IS NOT NULL ORDER BY reviewed_at, id"
    )
    added = 0
    for r in await cur.fetchall():
        applied = json.loads(r["applied"])
        if not applied:
            continue  # accepted as a case for the Assessor: nothing to apply
        reviewed = datetime.fromtimestamp(r["reviewed_at"] / 1000, tz=timezone.utc).astimezone(quotas.CHICAGO).strftime("%Y-%m-%d")
        prior = entries.get(r["pin10"], {})
        ids = sorted({*prior.get("report_ids", []), int(r["id"])})
        if r["id"] not in prior.get("report_ids", []):
            added += 1
        stories = applied.get("stories")
        entries[r["pin10"]] = {
            "stories": stories,
            "empty": bool(applied.get("empty")),
            "reviewed": reviewed,
            "report_ids": ids,
            "what": r["review_note"] or (f"{stories} stories" if stories else "no building"),
        }
    content = _dump(entries)
    before = _dump(committed) if committed else ""
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), content.splitlines(keepends=True),
        fromfile="a/backend/discovery/user_corrections.json", tofile="b/backend/discovery/user_corrections.json",
    ))
    return {"content": content, "diff": diff, "entries": len(entries), "new_reports": added}


