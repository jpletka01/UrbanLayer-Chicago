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
