"""Saved (Phase 9, decision Item 119): a signed-in user's saved lots and saved Discovery searches.

Every route needs a signed-in user and every statement is scoped ``WHERE user_id = ?``: another user's id answers
404, never 403, so ids can't be probed. Bodies forbid unknown fields, so a client can't set ``user_id`` or a
snapshot. What a lot looked like when it was saved (its zoning, overlays and passed ordinances) is taken by the
server from the Profile's own lookups, never from the client.

"What changed since it was saved" is computed on demand, one lot per request, with no model calls:
  * records dated after the save day: sales (County, by PIN), building permits and violations (City, by address),
    and a rezoning filed on the lot (the Clerk's pending docket, already on disk);
  * zoning, overlays and passed ordinances: the "since then" diff (``data_health/diff.py``) against the baseline
    taken at the lot's first check, whose lookups are cached once per parcel per day (``fact_checks``).
A source that failed is listed as unchecked, never read as "nothing changed".
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import db
from backend.auth import _auth_enabled, require_auth
from backend.rate_limit import check_saved_limit
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saved", tags=["saved"])

MAX_LOTS = 200
MAX_SEARCHES = 20
MAX_NOTE = 2000
MAX_NAME = 80
MAX_OUTLINE_POINTS = 40
MAX_DRAFT_BYTES = 16_000
# A saved search keeps its matching PINs only up to this many (about 60 KB gzipped); a broader search keeps its
# count, and "new matches" then reads as a change in the count.
MAX_STORED_PINS = 20_000
# Chicago's box with a margin: anything outside is not a lot we can show.
LON_RANGE = (-88.0, -87.4)
LAT_RANGE = (41.6, 42.1)
# The zoning facts a saved lot reports; the diff's code-text and correction notes belong to chat answers.
LOT_CHANGE_KINDS = {"district", "overlay", "standards", "map_amendment", "designation"}

_PIN = re.compile(r"^\d{14}$")
# Records at an address, fetched once per hour per address (the City's and County's own caches sit below).
_records_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="saved_records")
# At most this many "what changed" checks run at once for the whole app.
_check_slots: asyncio.Semaphore | None = None


def _slots() -> asyncio.Semaphore:
    global _check_slots
    if _check_slots is None:
        _check_slots = asyncio.Semaphore(4)
    return _check_slots


def _now_ms() -> int:
    return int(time.time() * 1000)


_CHICAGO = ZoneInfo("America/Chicago")


def _day(ms: int) -> str:
    """The day a save happened, in Chicago (the City's records are dated in Chicago, and so is the card)."""
    return datetime.fromtimestamp(ms / 1000, tz=_CHICAGO).strftime("%Y-%m-%d")


def lot_key(pin: str | None, address: str) -> str:
    """The same rule as the browser's ``lotMemory.lotKey``: by PIN when known, else by the address."""
    return f"pin:{pin}" if pin else f"addr:{address.strip().lower()}"


async def _owner(user: dict) -> str:
    """The signed-in user's id. With sign-in turned off (local development) the stand-in user has no users row,
    which the saved tables reference, so it gets one."""
    if not _auth_enabled():
        conn = db._get_db()
        now = _now_ms()
        await conn.execute(
            "INSERT OR IGNORE INTO users (id, email, name, google_id, tier, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], user.get("email") or "dev@example.com", user.get("name") or "Developer", user.get("google_id") or user["id"],
             "admin" if user.get("tier") == "admin" else "free", now, now),
        )
        await conn.commit()
    return user["id"]


# ── Bodies ────────────────────────────────────────────────────────────────────────────────────────────────────

class LotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: str | None = None
    address: str = Field(min_length=1, max_length=200)
    lat: float
    lon: float
    zone: str | None = Field(default=None, max_length=20)
    area: str | None = Field(default=None, max_length=60)
    outline: list[list[float]] | None = None
    # Only a merge of the browser's saves carries this: when the lot was saved there (epoch ms).
    saved_at: int | None = None
    # The address is a neighbor's stand-in (Discovery's "~", Item 109): shown as "Near …", never used to look up
    # the City's records at an address, which would be the neighbor's.
    approximate: bool = False

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.replace("-", "").strip()
        if not _PIN.match(v):
            raise ValueError("pin must be 14 digits")
        return v

    @field_validator("address")
    @classmethod
    def _address(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("address is empty")
        return v

    @field_validator("lat")
    @classmethod
    def _lat(cls, v: float) -> float:
        if not LAT_RANGE[0] <= v <= LAT_RANGE[1]:
            raise ValueError("lat outside Chicago")
        return v

    @field_validator("lon")
    @classmethod
    def _lon(cls, v: float) -> float:
        if not LON_RANGE[0] <= v <= LON_RANGE[1]:
            raise ValueError("lon outside Chicago")
        return v

    @field_validator("outline")
    @classmethod
    def _outline(cls, v: list[list[float]] | None) -> list[list[float]] | None:
        if v is None:
            return None
        if not 3 <= len(v) <= MAX_OUTLINE_POINTS:
            raise ValueError("outline must have 3 to 40 points")
        for p in v:
            if len(p) != 2 or not (LON_RANGE[0] <= p[0] <= LON_RANGE[1] and LAT_RANGE[0] <= p[1] <= LAT_RANGE[1]):
                raise ValueError("outline point outside Chicago")
        return [[round(p[0], 6), round(p[1], 6)] for p in v]


class MergeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lots: list[LotIn] = Field(max_length=MAX_LOTS)


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(max_length=MAX_NOTE)


class SearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME)
    # The page's own draft (what it restores when the search is reopened): opaque here, size-limited.
    draft: dict[str, Any]
    # The compiled request the server evaluates, the same envelope Discovery's search sends.
    request: dict[str, Any]


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME)


# ── Lots ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _lot_out(row: Any) -> dict:
    display = json.loads(row["display_json"] or "{}")
    return {
        "id": row["id"],
        "key": row["lot_key"],
        "pin": row["pin"],
        "address": row["address"],
        "lat": row["lat"],
        "lon": row["lon"],
        "zone": display.get("zone"),
        "area": display.get("area"),
        "outline": display.get("outline"),
        "approximate": bool(display.get("approximate")),
        "note": row["note"],
        "saved_at": row["saved_at"],
        "watching_since": _baseline_day(row["snapshot_json"]),
    }


def _approximate(row: Any) -> bool:
    try:
        return bool(json.loads(row["display_json"] or "{}").get("approximate"))
    except ValueError:
        return False


def _baseline_day(snapshot_json: str | None) -> str | None:
    if not snapshot_json:
        return None
    try:
        return (json.loads(snapshot_json).get("answered_at") or "")[:10] or None
    except ValueError:
        return None


async def _list_lots(uid: str) -> list[dict]:
    cur = await db._get_db().execute(
        "SELECT * FROM saved_lots WHERE user_id = ? ORDER BY saved_at DESC, id", (uid,),
    )
    return [_lot_out(r) for r in await cur.fetchall()]


async def _get_lot(uid: str, lot_id: str) -> Any:
    cur = await db._get_db().execute("SELECT * FROM saved_lots WHERE id = ? AND user_id = ?", (lot_id, uid))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


async def _insert_lots(uid: str, lots: list[LotIn], *, keep_times: bool) -> tuple[int, int]:
    """Insert lots not already saved (by key), newest first, up to the cap, in one transaction. Returns
    (added, skipped for the cap). Two tabs merging at once can't duplicate a lot: the key is unique per user."""
    conn = db._get_db()
    now = _now_ms()
    oldest = now - 365 * 86_400_000
    added = skipped = 0
    ordered = sorted(lots, key=lambda lot: -(lot.saved_at or now))
    await conn.execute("BEGIN IMMEDIATE")
    try:
        cur = await conn.execute("SELECT COUNT(*) FROM saved_lots WHERE user_id = ?", (uid,))
        count = (await cur.fetchone())[0]
        for lot in ordered:
            key = lot_key(lot.pin, lot.address)
            cur = await conn.execute("SELECT 1 FROM saved_lots WHERE user_id = ? AND lot_key = ?", (uid, key))
            if await cur.fetchone():
                continue
            if count >= MAX_LOTS:
                skipped += 1
                continue
            saved_at = min(max(lot.saved_at, oldest), now) if keep_times and lot.saved_at else now
            display = {"zone": lot.zone, "area": lot.area, "outline": lot.outline, "approximate": lot.approximate}
            await conn.execute(
                "INSERT OR IGNORE INTO saved_lots (id, user_id, lot_key, pin, address, lat, lon, display_json, saved_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (secrets.token_urlsafe(12), uid, key, lot.pin, lot.address, lot.lat, lot.lon,
                 json.dumps(display, separators=(",", ":")), saved_at, now),
            )
            count += 1
            added += 1
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return added, skipped


@router.get("/lots")
async def list_lots(user: dict = Depends(require_auth)) -> dict:
    uid = await _owner(user)
    return {"lots": await _list_lots(uid), "max": MAX_LOTS}


@router.post("/lots")
async def save_lot(body: LotIn, response: Response, user: dict = Depends(require_auth)) -> dict:
    uid = await _owner(user)
    check_saved_limit(uid, "write", 60)
    added, skipped = await _insert_lots(uid, [body.model_copy(update={"saved_at": None})], keep_times=False)
    if skipped:
        raise HTTPException(status_code=409, detail={"error": "saved_limit", "max": MAX_LOTS})
    response.status_code = 201 if added else 200
    key = lot_key(body.pin, body.address)
    cur = await db._get_db().execute("SELECT * FROM saved_lots WHERE user_id = ? AND lot_key = ?", (uid, key))
    return _lot_out(await cur.fetchone())


@router.post("/lots/merge")
async def merge_lots(body: MergeIn, user: dict = Depends(require_auth)) -> dict:
    """The browser's saves after sign-in: added once (by key), keeping when each was saved; safe to repeat."""
    uid = await _owner(user)
    check_saved_limit(uid, "merge", 10)
    added, skipped = await _insert_lots(uid, body.lots, keep_times=True)
    return {"added": added, "skipped": skipped, "lots": await _list_lots(uid), "max": MAX_LOTS}


@router.patch("/lots/{lot_id}")
async def edit_note(lot_id: str, body: NoteIn, user: dict = Depends(require_auth)) -> dict:
    uid = await _owner(user)
    check_saved_limit(uid, "write", 60)
    await _get_lot(uid, lot_id)
    conn = db._get_db()
    await conn.execute(
        "UPDATE saved_lots SET note = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (body.note.strip(), _now_ms(), lot_id, uid),
    )
    await conn.commit()
    return _lot_out(await _get_lot(uid, lot_id))


@router.delete("/lots/{lot_id}", status_code=204)
async def unsave_lot(lot_id: str, user: dict = Depends(require_auth)) -> Response:
    uid = await _owner(user)
    check_saved_limit(uid, "write", 60)
    conn = db._get_db()
    cur = await conn.execute("DELETE FROM saved_lots WHERE id = ? AND user_id = ?", (lot_id, uid))
    await conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(status_code=204)


# ── What changed on a saved lot ───────────────────────────────────────────────────────────────────────────────

async def _records(pin: str | None, address: str, approximate: bool = False) -> dict[str, Any]:
    """Sales, permits and violations at the lot, each list or None when its lookup failed. Cached an hour. A lot whose
    address is a neighbor's stand-in gets no address lookups (``no_address``): those records would be the neighbor's."""
    from backend.retrieval import buildings
    from backend.retrieval.property.sales import get_sales

    key = f"{pin or '-'}|{address.lower()}"
    hit = _records_cache.get(key)
    if hit is not None:
        return hit

    async def none() -> list:
        return []

    if approximate:
        try:
            sales = list(await get_sales(pin)) if pin else []
        except Exception:
            log.warning("Saved: sales lookup failed")
            sales = None
        out_approx = {"sales": sales, "permits": [], "violations": [], "no_address": True}
        if sales is not None:
            _records_cache.set(key, out_approx)
        return out_approx

    got = await asyncio.gather(
        get_sales(pin) if pin else none(),
        buildings.permits_at_address(address),
        buildings.violations_at_address(address),
        return_exceptions=True,
    )
    out: dict[str, Any] = {}
    for name, value in zip(("sales", "permits", "violations"), got):
        if isinstance(value, BaseException):
            log.warning("Saved: %s lookup failed", name)
            out[name] = None
        elif name == "sales":
            out[name] = list(value or [])
        elif value is None:
            # The address could not be read into street fields: nothing was asked, so nothing can be said.
            out[name] = None
        else:
            out[name] = list(value.get("projects" if name == "permits" else "violations") or [])
    if all(v is not None for v in out.values()):
        _records_cache.set(key, out)
    return out


def _price(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def record_changes(records: dict[str, Any], since: str) -> tuple[list[dict], list[str]]:
    """The records dated after ``since`` (YYYY-MM-DD), newest first, and the sources that could not be read."""
    changes: list[dict] = []
    unchecked: list[str] = []
    if records.get("sales") is None:
        unchecked.append("sales")
    for s in records.get("sales") or []:
        day = (s.get("sale_date") or "")[:10]
        if day > since:
            changes.append({"kind": "sale", "date": day, "price": _price(s.get("sale_price"))})
    if records.get("no_address"):
        unchecked.append("no_address")
    if records.get("permits") is None:
        unchecked.append("permits")
    for p in records.get("permits") or []:
        day = p.get("issued") or ""
        if day > since:
            changes.append({"kind": "permit", "date": day, "permit": p.get("permit"), "permit_type": p.get("permit_type"),
                            "description": p.get("description"), "cost": p.get("cost")})
    if records.get("violations") is None:
        unchecked.append("violations")
    seen_inspections: set[str] = set()
    for v in records.get("violations") or []:
        day = v.get("date") or ""
        if day <= since:
            continue
        # One line per inspection: an inspection usually writes several violations on one day.
        ins = v.get("inspection") or f"{day}|{v.get('code')}"
        if ins in seen_inspections:
            continue
        seen_inspections.add(ins)
        changes.append({"kind": "violation", "date": day, "code": v.get("code"), "description": v.get("description"),
                        "status": v.get("status")})
    return changes, unchecked


def _rezoning_filed(row: Any, since: str) -> tuple[list[dict], bool]:
    """Rezoning filings placed on this lot and introduced after ``since``; False when the docket is unavailable."""
    from backend.config import get_settings
    from backend.legislation.upcoming import summary_for

    s = summary_for(
        get_settings().pending_legislation_path, lat=row["lat"], lon=row["lon"], pin=row["pin"],
        address=None if _approximate(row) else row["address"], authoritative_pin=bool(row["pin"]),
    )
    if s.status == "unavailable":
        return [], False
    out = []
    for f in s.subject_filings:
        day = (f.introduced_at or "")[:10]
        if day > since:
            out.append({"kind": "rezoning_filed", "date": day, "record": f.record_number, "title": f.title, "url": f.url})
    return out, True


async def _zoning_changes(uid: str, row: Any) -> tuple[list[dict], list[str], str | None]:
    """Zoning, overlays and passed ordinances against the lot's baseline; the first check takes the baseline."""
    from backend.data_health import diff

    if not row["snapshot_json"]:
        point = {"lat": row["lat"], "lon": row["lon"], "address": row["address"], "pin": row["pin"]}
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        key = diff.check_key(point)
        cur = await db.get_fact_check(key, day) if key else None
        if cur is None:
            try:
                cur = await diff.current_facts(point)
            except Exception:
                log.warning("Saved: baseline lookup failed", exc_info=True)
                cur = None
        checked = (cur or {}).get("checked") or {}
        if cur is None or not checked.get("zoning") or checked.get("unchecked_overlays"):
            return [], ["zoning"], None
        if key:
            await db.put_fact_check(key, day, cur)
        baseline = {k: v for k, v in cur.items() if k not in ("checked", "passed_detail", "overlay_labels")}
        baseline.update(point)  # the re-check looks at the saved lot's own point
        baseline["answered_at"] = now.isoformat(timespec="seconds")
        conn = db._get_db()
        await conn.execute(
            "UPDATE saved_lots SET snapshot_json = ? WHERE id = ? AND user_id = ? AND snapshot_json IS NULL",
            (json.dumps(baseline, separators=(",", ":")), row["id"], uid),
        )
        await conn.commit()
        return [], [], day
    old = json.loads(row["snapshot_json"])
    res = await diff.changes_for(old)
    changes = [{**c, "date": c.get("passed_on")} for c in res.get("changes") or [] if c.get("kind") in LOT_CHANGE_KINDS]
    unchecked = ["zoning"] if res.get("status") == "unavailable" or res.get("unchecked") else []
    return changes, unchecked, (old.get("answered_at") or "")[:10] or None


@router.get("/lots/{lot_id}/changes")
async def lot_changes(lot_id: str, user: dict = Depends(require_auth)) -> dict:
    """What changed on one saved lot since it was saved (see the module docstring)."""
    uid = await _owner(user)
    row = await _get_lot(uid, lot_id)
    check_saved_limit(uid, "changes", 120)
    since = _day(row["saved_at"])
    async with _slots():
        records, (zoning, z_unchecked, watching) = await asyncio.gather(
            _records(row["pin"], row["address"], _approximate(row)), _zoning_changes(uid, row),
        )
        try:
            filed, docket_ok = await asyncio.to_thread(_rezoning_filed, row, since)
        except Exception:
            log.warning("Saved: rezoning docket read failed", exc_info=True)
            filed, docket_ok = [], False
    changes, unchecked = record_changes(records, since)
    changes += zoning + filed
    unchecked += z_unchecked + ([] if docket_ok else ["rezoning"])
    changes.sort(key=lambda c: c.get("date") or "", reverse=True)
    status = "changes" if changes else ("partial" if unchecked else "none")
    return {"since": since, "watching_since": watching, "status": status, "changes": changes, "unchecked": unchecked}


# ── Searches ──────────────────────────────────────────────────────────────────────────────────────────────────

def _evaluate(request: dict[str, Any]) -> tuple[dict, str, list[str]]:
    """Run a saved request through Discovery's single search path: the canonical query, the data version and the
    ordered matching PINs. Raises 422 for a request Discovery would reject, 503 when no index is installed."""
    from backend.discovery import api as discovery_api

    try:
        req = discovery_api.SearchRequest(**{k: v for k, v in request.items() if k not in (
            "limit", "offset", "includePins", "includeAreaCounts", "registryVersion")})
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Not a Discovery search") from exc
    try:
        cqs, result, _dropped, version = discovery_api._resolve(req)
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("Saved: search evaluation failed", exc_info=True)
        raise HTTPException(status_code=503, detail="Discovery is unavailable") from exc
    return cqs.model_dump(mode="json"), version, list(result.pins)


def _pack(pins: list[str]) -> bytes | None:
    if len(pins) > MAX_STORED_PINS:
        return None
    return gzip.compress("\n".join(sorted(pins)).encode())


def _unpack(blob: bytes | None) -> set[str] | None:
    if blob is None:
        return None
    text = gzip.decompress(blob).decode()
    return set(text.split("\n")) if text else set()


def _search_out(row: Any) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "draft": json.loads(row["draft_json"]),
        "cqs": json.loads(row["cqs_json"]),
        "match_count": row["match_count"],
        "saved_at": row["saved_at"],
        "seen_at": row["seen_at"],
    }


async def _get_search(uid: str, search_id: str) -> Any:
    cur = await db._get_db().execute("SELECT * FROM saved_searches WHERE id = ? AND user_id = ?", (search_id, uid))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.get("/searches")
async def list_searches(user: dict = Depends(require_auth)) -> dict:
    uid = await _owner(user)
    cur = await db._get_db().execute("SELECT * FROM saved_searches WHERE user_id = ? ORDER BY saved_at DESC, id", (uid,))
    return {"searches": [_search_out(r) for r in await cur.fetchall()], "max": MAX_SEARCHES}


@router.post("/searches", status_code=201)
async def save_search(body: SearchIn, user: dict = Depends(require_auth)) -> dict:
    uid = await _owner(user)
    check_saved_limit(uid, "write", 60)
    if len(json.dumps(body.draft)) > MAX_DRAFT_BYTES or len(json.dumps(body.request)) > MAX_DRAFT_BYTES:
        raise HTTPException(status_code=413, detail="Search too large")
    conn = db._get_db()
    cur = await conn.execute("SELECT COUNT(*) FROM saved_searches WHERE user_id = ?", (uid,))
    if (await cur.fetchone())[0] >= MAX_SEARCHES:
        raise HTTPException(status_code=409, detail={"error": "saved_limit", "max": MAX_SEARCHES})
    cqs, version, pins = await asyncio.to_thread(_evaluate, body.request)
    now = _now_ms()
    sid = secrets.token_urlsafe(12)
    await conn.execute(
        "INSERT INTO saved_searches (id, user_id, name, draft_json, request_json, cqs_json, data_version, match_count,"
        " match_pins_gz, saved_at, seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, uid, " ".join(body.name.split()), json.dumps(body.draft, separators=(",", ":")),
         json.dumps(body.request, separators=(",", ":")), json.dumps(cqs, separators=(",", ":")), version,
         len(pins), _pack(pins), now, now),
    )
    await conn.commit()
    return _search_out(await _get_search(uid, sid))


@router.get("/searches/{search_id}/new")
async def search_new(search_id: str, user: dict = Depends(require_auth)) -> dict:
    """How many lots match now that didn't when the search was saved (or last seen)."""
    uid = await _owner(user)
    row = await _get_search(uid, search_id)
    check_saved_limit(uid, "changes", 120)
    _cqs, version, pins = await asyncio.to_thread(_evaluate, json.loads(row["request_json"]))
    before = _unpack(row["match_pins_gz"])
    if before is not None and len(pins) <= MAX_STORED_PINS:
        new = len(set(pins) - before)
        gone = len(before - set(pins))
        exact = True
    else:
        new = max(0, len(pins) - row["match_count"])
        gone = max(0, row["match_count"] - len(pins))
        exact = False
    return {"total": len(pins), "new": new, "gone": gone, "exact": exact,
            "same_data": version == row["data_version"], "since": _day(row["seen_at"])}


@router.post("/searches/{search_id}/seen")
async def search_seen(search_id: str, user: dict = Depends(require_auth)) -> dict:
    """The user looked at the matches: they become the new "before"."""
    uid = await _owner(user)
    row = await _get_search(uid, search_id)
    check_saved_limit(uid, "write", 60)
    _cqs, version, pins = await asyncio.to_thread(_evaluate, json.loads(row["request_json"]))
    conn = db._get_db()
    await conn.execute(
        "UPDATE saved_searches SET data_version = ?, match_count = ?, match_pins_gz = ?, seen_at = ? WHERE id = ? AND user_id = ?",
        (version, len(pins), _pack(pins), _now_ms(), search_id, uid),
    )
    await conn.commit()
    return _search_out(await _get_search(uid, search_id))


@router.patch("/searches/{search_id}")
async def rename_search(search_id: str, body: NameIn, user: dict = Depends(require_auth)) -> dict:
    uid = await _owner(user)
    check_saved_limit(uid, "write", 60)
    await _get_search(uid, search_id)
    conn = db._get_db()
    await conn.execute("UPDATE saved_searches SET name = ? WHERE id = ? AND user_id = ?", (" ".join(body.name.split()), search_id, uid))
    await conn.commit()
    return _search_out(await _get_search(uid, search_id))


@router.delete("/searches/{search_id}", status_code=204)
async def delete_search(search_id: str, user: dict = Depends(require_auth)) -> Response:
    uid = await _owner(user)
    check_saved_limit(uid, "write", 60)
    conn = db._get_db()
    cur = await conn.execute("DELETE FROM saved_searches WHERE id = ? AND user_id = ?", (search_id, uid))
    await conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(status_code=204)
