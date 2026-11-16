"""Entitlements (Phase 9 epic 4, decision Item 123): the one free Deep analysis.

Every signed-in account gets one Deep analysis free, for one lot; Pro and admin have them without limit. Once used,
that lot stays open to the person for good (its Deep analysis and its PDF), like a bought report.

It follows the person, not the account row, the way the month's question count does (Item 121): a use is stored
under ``user:<id>`` and under ``idh:<HMAC of each linked sign-in identity>``. Deleting the account drops the
``user:`` row only; signing in again with the same Google/Apple/Microsoft account finds the identity row, and so
does an identity linked later (``carry_on_link``), so moving identities between accounts never hands out a second.
"""

from __future__ import annotations

import logging
import time

from fastapi import HTTPException

from backend import db
from backend.quotas import identity_subject

log = logging.getLogger(__name__)

KIND = "deep_analysis_free"


def _unlimited(user: dict | None) -> bool:
    return bool(user) and user.get("tier") in ("premium", "admin")


def same_lot(a: str | None, b: str | None) -> bool:
    """Two PINs are the same lot when their first ten digits match: the last four number a condo unit or a
    leasehold on that lot (Item 124), so the free analysis claimed through one unit opens the lot through any."""
    return bool(a) and bool(b) and a[:10] == b[:10]


async def free_address(pin: str | None) -> str | None:
    """The free lot's address for Settings and the tab ("went to <address>"). Display only; None when the County
    has none or the lookup fails (the page then shows the PIN)."""
    if not pin:
        return None
    try:
        from backend.retrieval.property.address_points import pin_to_address
        return await pin_to_address(pin)
    except Exception:
        log.warning("free deep analysis address lookup failed", exc_info=True)
        return None


def _user_subject(user_id: str) -> str:
    return f"user:{user_id}"


async def _subjects(user_id: str) -> list[str]:
    subjects = [_user_subject(user_id)]
    for ident in await db.list_identities(user_id):
        subjects.append(identity_subject(ident["provider"], ident["subject"]))
    return subjects


async def free_pin(user_id: str) -> str | None:
    """The lot this person's free Deep analysis went to, if they used it (under this account or an identity)."""
    subjects = await _subjects(user_id)
    marks = ",".join("?" for _ in subjects)
    cur = await db._get_db().execute(
        f"SELECT pin FROM entitlement_uses WHERE kind = ? AND subject IN ({marks}) ORDER BY used_at LIMIT 1",
        (KIND, *subjects),
    )
    row = await cur.fetchone()
    return row["pin"] if row else None


async def status(user: dict | None) -> dict:
    """``GET /api/entitlements``."""
    if not user:
        return {"signed_in": False, "deep_analysis": {
            "unlimited": False, "free_left": 0, "free_pin": None, "free_address": None}}
    pin = await free_pin(user["id"])
    return {
        "signed_in": True,
        "deep_analysis": {
            "unlimited": _unlimited(user),
            "free_left": 0 if pin else 1,
            "free_pin": pin,
            "free_address": await free_address(pin),
        },
    }


async def claim(user: dict, pin: str) -> dict:
    """Use the free Deep analysis on ``pin``. Pro/admin consume nothing. The same lot again is fine; another lot
    after it is used is a 409. Two claims at once: the account's row is the unique key, so one wins."""
    if _unlimited(user):
        return {"ok": True, "pin": pin, "unlimited": True}
    used = await free_pin(user["id"])
    if used:
        if same_lot(used, pin):
            return {"ok": True, "pin": used, "unlimited": False}
        raise HTTPException(status_code=409, detail={"error": "free_used", "free_pin": used})

    conn = db._get_db()
    now = int(time.time() * 1000)
    cur = await conn.execute(
        "INSERT OR IGNORE INTO entitlement_uses (subject, kind, pin, used_at) VALUES (?, ?, ?, ?)",
        (_user_subject(user["id"]), KIND, pin, now),
    )
    await conn.commit()
    if cur.rowcount != 1:
        used = await free_pin(user["id"])
        if same_lot(used, pin):
            return {"ok": True, "pin": used, "unlimited": False}
        raise HTTPException(status_code=409, detail={"error": "free_used", "free_pin": used})
    for subject in (await _subjects(user["id"]))[1:]:
        await conn.execute(
            "INSERT OR IGNORE INTO entitlement_uses (subject, kind, pin, used_at) VALUES (?, ?, ?, ?)",
            (subject, KIND, pin, now),
        )
    await conn.commit()
    log.info("free deep analysis claimed user=%s", user["id"])
    return {"ok": True, "pin": pin, "unlimited": False}


async def carry_on_link(user_id: str, provider: str, subject: str) -> None:
    """A sign-in identity just linked to an account that has used its free analysis carries the use too."""
    pin = await free_pin(user_id)
    if not pin:
        return
    conn = db._get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO entitlement_uses (subject, kind, pin, used_at) VALUES (?, ?, ?, ?)",
        (identity_subject(provider, subject), KIND, pin, int(time.time() * 1000)),
    )
    await conn.commit()


async def opens_lot(user: dict, pin: str | None) -> bool:
    """True when this lot's Deep analysis (and PDF) is open to the account: Pro/admin, or its free lot."""
    if _unlimited(user):
        return True
    return bool(pin) and same_lot(await free_pin(user["id"]), pin)
