"""The Property Profile in parts (front-end rewrite Phase 4, decision Item 89).

The new Profile asks for its **Overview** first and the slower parts after the Overview is on screen:

``GET /api/profile/overview?address|pin|lat&lon`` resolves the parcel once, reconciles its identity, and fetches
what the Overview reads (the core property record, the zoning point, overlays and flood, program membership,
Walk Score). It returns a signed ``lookup`` token and the Profile so far.

``GET /api/profile/part/{name}?lookup=…&have=…`` fetches one late part and never resolves the address again:
``building`` (the City portal's building records: energy benchmarking, footprints; the Overview's slow tail,
owner's call), ``history`` (parcel flags, appeals, Assessor permits), ``money`` (comparables), ``incentives`` (TIF reports,
grants), ``neighborhood`` (tract, transit, traffic, Divvy, rent), ``activity`` (crime, 311, violations, ARO),
``block_face`` (RS-3 only).

**One record per lookup.** Every part writes its raw results into an in-memory record keyed by the token, and
every response is the Profile assembled from everything the record holds, by the full response's own functions
(``main._scorecard_data_from`` + ``main._finish_scorecard_payload``). So the derived figures that read several
parts (unit yield, code currency, coverage notes, provenance, data dates) are always computed from all the facts
known, and once every part is in, the Profile equals ``/api/scorecard``'s (``test_profile_parts.py``). The page
keeps the response with the highest ``version``. A record the server lost (restart, eviction) is rebuilt from the
token: the Overview's calls again (cached), the parts the page says it ``have``, then the one asked.

**Late sources have a deadline** (``LATE_DEADLINE_S``, 20 s, the owner's call): a source past it is listed in
``timed_out`` and absent from the Profile (the page says "Couldn't check in time", never "none"); the fetch
keeps running so its cache fills, and a Retry joins it or finds it cached (``backend/inflight.py``). Late parts
share a small concurrency cap so one visitor's late burst doesn't slow another visitor's Overview. A visitor who
leaves cancels the work nobody else is waiting for.

The full ``/api/scorecard`` is unchanged and stays the source for today's Profile, chat grounding and the report.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request

from backend import inflight
from backend import timing as _timing
from backend.config import get_settings
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

LATE_PARTS = ("building", "history", "money", "incentives", "neighborhood", "activity", "block_face")
PARTS = ("overview", *LATE_PARTS)
LATE_DEADLINE_S = 20.0
LATE_CONCURRENCY = 8  # today's response's parallelism (main._RETRIEVAL_SEM); 4 made the whole Profile slower
LOOKUP_TTL_S = 1800

_records = TTLCache(ttl_seconds=LOOKUP_TTL_S, maxsize=256, name="profile_lookups")
_late_sem: asyncio.Semaphore | None = None


def _late_semaphore() -> asyncio.Semaphore:
    global _late_sem
    if _late_sem is None:
        _late_sem = asyncio.Semaphore(LATE_CONCURRENCY)
    return _late_sem


# ── The lookup token ───────────────────────────────────────────────────────────────────────────────────

def _secret() -> bytes:
    from backend.config import _DEV_JWT_SECRET

    return ("profile-lookup:" + (get_settings().jwt_secret or _DEV_JWT_SECRET)).encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_lookup(claims: dict) -> str:
    body = _b64(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    mac = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{mac}"


def read_lookup(token: str) -> dict:
    """The token's claims; a 409 when it is malformed, forged or expired (the page then asks the Overview again).
    Signed because the parts trust its identity: which PIN and how sure, the same rule as "never construct
    identity client-side"."""
    try:
        body, mac = token.split(".", 1)
        good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, good):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(body))
        if float(claims["exp"]) < time.time():
            raise ValueError("expired")
        return claims
    except Exception as exc:  # noqa: BLE001 - every bad token is the same answer
        raise HTTPException(status_code=409, detail="This lookup has expired. Load the profile again.") from exc


# ── The record ─────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Record:
    id: str
    address_in: str | None
    rl: Any  # main.ResolvedLocation
    identity: Any  # main.ProfileIdentity
    ca: int | None
    ca_name: str | None
    ap_pins: list[str] = field(default_factory=list)
    assessor_pins: list[str] = field(default_factory=list)
    # Every parcel the address sources list for a typed address (the "how we found this parcel" panel, read only
    # in Sources): started with the Overview, never waited for by it; the late parts take it when it's in.
    cand_task: Any = None
    cand_applies: bool = False
    results: dict[str, Any] = field(default_factory=dict)
    comparables: Any = None
    block_face: Any = None
    parts_in: set[str] = field(default_factory=set)
    timed_out: dict[str, list[str]] = field(default_factory=dict)
    version: int = 0


def _claims(rec: Record) -> dict:
    rl, idn = rec.rl, rec.identity
    return {
        "i": rec.id, "a": rec.address_in,
        "rl": [rl.lat, rl.lon, rl.address, rl.pin, rl.confidence, rl.method],
        "id": [idn.pin, idn.confidence, idn.method, idn.unverified, idn.unverified_reason],
        "ap": rec.ap_pins, "as": rec.assessor_pins, "c": rec.cand_applies,
        "exp": int(time.time()) + LOOKUP_TTL_S,
    }


def _record_from_claims(claims: dict) -> Record:
    from backend.main import ProfileIdentity, ResolvedLocation
    from backend.retrieval.geo import community_area_by_point, community_area_name

    rl = ResolvedLocation(*claims["rl"])
    ca = community_area_by_point(rl.lat, rl.lon)
    return Record(
        id=claims["i"], address_in=claims.get("a"), rl=rl, identity=ProfileIdentity(*claims["id"]),
        ca=ca, ca_name=community_area_name(ca) if ca else None,
        ap_pins=list(claims.get("ap") or []), assessor_pins=list(claims.get("as") or []),
        cand_applies=bool(claims.get("c")),
    )


async def _take_candidates(rec: Record, wait_s: float) -> None:
    """Move the address candidates into the record once their lookup is in (waiting up to ``wait_s``)."""
    t = rec.cand_task
    if t is None:
        return
    if not t.done() and wait_s > 0:
        await asyncio.wait({t}, timeout=wait_s)
    if not t.done():
        return
    rec.cand_task = None
    got = t.result()
    rec.ap_pins = got[0] if isinstance(got[0], list) else []
    rec.assessor_pins = got[1] if isinstance(got[1], list) else []


# ── What each part runs ────────────────────────────────────────────────────────────────────────────────

def _overview_coros(rec: Record) -> dict[str, Any]:
    """The Overview's tasks (main.SCORECARD_TASK_KEYS order): the core property record (no History lookups),
    regulatory, the zoning point, program membership and Walk Score. Same `_limited` names as the full path."""
    from backend import main
    from backend.retrieval.incentives import incentives_membership
    from backend.retrieval.neighborhood import walkscore_summary
    from backend.retrieval.property import property_core

    rl = rec.rl
    coros: dict[str, Any] = {
        "property": main._limited(property_core(
            rl.lat, rl.lon, pin=rl.pin, workflow="property_intelligence", city_building_facts=False,
        ), "property"),
        "regulatory": main._scorecard_task("regulatory", rl.lat, rl.lon, rl.address, pin=rl.pin, ca=rec.ca, ca_name=rec.ca_name),
        "zoning": inflight.shared(("zoning", rl.lat, rl.lon), lambda: main._limited(main.lookup_zoning(rl.lat, rl.lon), "zoning")),
    }
    if rec.ca is not None:
        coros["incentives"] = main._limited(incentives_membership(rl.lat, rl.lon), "incentives")
        coros["neighborhood"] = main._limited(walkscore_summary(rl.lat, rl.lon, rl.address), "neighborhood")
    return coros


async def _gather_into(rec: Record, coros: dict[str, Any]) -> None:
    done = await asyncio.gather(*coros.values(), return_exceptions=True)
    for key, value in zip(coros.keys(), done):
        if isinstance(value, BaseException) and not isinstance(value, Exception):
            raise value
        rec.results[key] = value


def _context(rec: Record):
    """The record's context as the full path builds it (for the parts that read the zoning and the class)."""
    from backend import main

    rl = rec.rl
    return main._scorecard_data_from(
        rec.results, rl.lat, rl.lon, rl.address, ca=rec.ca, ca_name=rec.ca_name,
    )["context"]


def applicable_parts(rec: Record) -> list[str]:
    """The late parts this parcel has: no History without a property record, no Money without a class (the
    comparables need it), no area parts without a community area, no block face outside RS-3. Read from the raw
    results (no assembly), by the same tests the full path applies."""
    prop = rec.results.get("property")
    prop = None if isinstance(prop, Exception) else prop
    zoning = rec.results.get("zoning")
    zone_class = zoning.get("zone_class") if isinstance(zoning, dict) else None
    out: list[str] = []
    if prop is not None and getattr(prop, "city_building_pending", False):
        out.append("building")
    if prop is not None and prop.pin14:
        out.append("history")
    if prop is not None and getattr(prop, "bldg_class", None):
        out.append("money")
    if rec.ca is not None:
        out += ["incentives", "neighborhood"]
    out.append("activity")
    # main._block_face_applies, on the zoning row the context's parcel_zoning is built from
    if (zone_class or "").strip().upper() == "RS-3" and rec.rl.address:
        out.append("block_face")
    return out


async def _late_source(key: tuple, factory, deadline_s: float) -> tuple[bool, Any]:
    """One late source: shared with any caller asking the same thing, under the late cap, with the deadline.
    ``(False, None)`` = past the deadline; an exception is returned as the value (the record names it)."""

    async def run(mark_started):
        async with _late_semaphore():
            mark_started()  # the deadline counts from here, not from the queue
            return await factory()

    try:
        return await inflight.shared_with_deadline(key, run, deadline_s)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - a failed source is recorded, never raised to the page
        return True, exc


async def _run_late(rec: Record, part: str, deadline_s: float) -> list[str]:
    """Run one late part into the record; the sources past the deadline."""
    from backend import main
    from backend.retrieval.property import property_history

    rl = rec.rl
    timed_out: list[str] = []
    sources: dict[str, tuple[tuple, Any]] = {}
    if part == "building":
        from backend.retrieval.property import property_core

        # The whole core again with the City's building lookups: the County calls are cached by now, and the
        # summary is rebuilt by the same merge (assessor wins, fill-only), so it equals the full path's.
        sources["property"] = (
            ("property_core_full", rl.lat, rl.lon, rl.pin),
            lambda: main._limited(property_core(rl.lat, rl.lon, pin=rl.pin, workflow="property_intelligence"), "property.building"),
        )
    elif part == "history":
        prop = rec.results.get("property")
        pin14 = getattr(prop, "pin14", None)
        if pin14:
            sources["property_history"] = (
                ("property_history", pin14, rl.lat, rl.lon),
                lambda: main._limited(property_history(pin14, rl.lat, rl.lon, workflow="property_intelligence"), "property.history"),
            )
    elif part in ("incentives", "neighborhood"):
        sources[part] = (
            (part, rl.lat, rl.lon, rl.address, rec.ca),
            lambda: main._scorecard_task(part, rl.lat, rl.lon, rl.address, pin=rl.pin, ca=rec.ca, ca_name=rec.ca_name),
        )
    elif part == "activity":
        keys = ["violations", "address_311"]
        if rec.ca is not None:
            keys = ["aro_housing", "crime", "crime_yoy", *keys]
        for k in keys:
            sources[k] = (
                (k, rl.lat, rl.lon, rl.address, rec.ca),
                (lambda k=k: main._scorecard_task(k, rl.lat, rl.lon, rl.address, pin=rl.pin, ca=rec.ca, ca_name=rec.ca_name)),
            )
    elif part == "money":
        ctx = _context(rec)
        cls = getattr(ctx.property, "bldg_class", None)
        zone = ctx.parcel_zoning.zone_class if ctx.parcel_zoning else None
        sources["comparables"] = (("comparables", rl.lat, rl.lon, cls, zone), lambda: main._scorecard_comparables(ctx, rl.lat, rl.lon))
    elif part == "block_face":
        ctx = _context(rec)
        sources["block_face"] = (("block_face", rl.address), lambda: main._scorecard_block_face(ctx, rl.address))
    else:  # pragma: no cover - the endpoint validates names
        raise KeyError(part)

    names = list(sources)
    got = await asyncio.gather(*(_late_source(k, f, deadline_s) for k, f in sources.values()))
    for name, (in_time, value) in zip(names, got):
        if not in_time:
            timed_out.append(name)
            continue
        if name == "comparables":
            rec.comparables = value
        elif name == "block_face":
            rec.block_face = value
        else:
            rec.results[name] = value
    return timed_out


# ── Assembling a response ──────────────────────────────────────────────────────────────────────────────

def _assemble(rec: Record) -> dict:
    """The Profile's data from everything the record holds right now, by the full response's own assembly.
    Synchronous on purpose: no other part can write the record while it runs (see ``_respond``)."""
    from backend import main

    rl = rec.rl
    return main._scorecard_data_from(
        rec.results, rl.lat, rl.lon, rl.address, ca=rec.ca, ca_name=rec.ca_name,
        comparables=rec.comparables, block_face=rec.block_face,
    )


async def _finish(rec: Record, data: dict, ap_pins: list[str], assessor_pins: list[str]) -> dict:
    """The payload from assembled data by the full response's own finish, plus each sale's arm's-length flag
    (excluded from the full response's dump)."""
    from backend import main

    sales = list(getattr(data["context"].property, "sales_history", None) or [])
    payload = await main._finish_scorecard_payload(
        data, address=rec.address_in, rl=rec.rl, identity=rec.identity,
        ap_pins=ap_pins, assessor_pins=assessor_pins,
    )
    dumped = ((payload.get("context") or {}).get("property") or {}).get("sales_history") or []
    for row, sale in zip(dumped, sales):
        row["arms_length"] = sale.arms_length
    return payload


async def _respond(rec: Record, part: str, timed_out: list[str]) -> dict:
    """One response. The version is taken in the same synchronous step that snapshots the record, so it orders
    the data each response holds. The finish awaits (upcoming zoning and text impacts run in a thread), and
    stamping the version after it let a part that snapshotted the record BEFORE the incentives part landed take
    a higher version than the incentives response: the page, which keeps the highest version, then swapped the
    full incentives for the Overview's membership-only ones (decision Item 100)."""
    data = _assemble(rec)
    head = _stamp(rec, part, timed_out)
    profile = await _finish(rec, data, list(rec.ap_pins), list(rec.assessor_pins))
    return {**head, "profile": profile}


def _stamp(rec: Record, part: str, timed_out: list[str]) -> dict:
    rec.version += 1
    pending = [p for p in applicable_parts(rec) if p not in rec.parts_in]
    return {
        "part": part,
        "lookup": sign_lookup(_claims(rec)),
        "record": rec.id,
        "version": rec.version,
        "parts_in": sorted(rec.parts_in, key=PARTS.index),
        "parts_pending": pending,
        "timed_out": timed_out,
        # every source still past its deadline, by part, so a page that missed a response still knows
        "timed_out_by_part": {k: v for k, v in rec.timed_out.items() if v},
    }


async def _until_disconnected(request: Request | None, coro):
    """Run ``coro``; cancel it when the visitor goes away (the page aborts on leaving or on a new lookup)."""
    task = asyncio.ensure_future(coro)
    if request is None:
        return await task

    async def watch() -> None:
        while not task.done():
            if await request.is_disconnected():
                task.cancel()
                return
            await asyncio.sleep(0.5)

    watcher = asyncio.create_task(watch())
    try:
        return await task
    finally:
        watcher.cancel()


def _log(part: str, ok: bool, timer) -> None:
    spans = timer.summary()
    slowest = sorted(
        ((k, v["ms"]) for k, v in spans.items() if "." not in k and k not in ("resolution",)),
        key=lambda kv: -kv[1],
    )[:3]
    log.info(
        "scorecard part timings part=%s ok=%s total_ms=%.0f slowest=%s",
        part, ok, timer.now_ms(), ",".join(f"{k}:{ms:.0f}" for k, ms in slowest),
    )


def _with_timings(out: dict, timer) -> dict:
    settings = get_settings()
    if settings.profile_timings and settings.environment != "production":
        out["_timings"] = {"total_ms": round(timer.now_ms(), 1), "spans": timer.summary()}
    return out


# ── The two operations ─────────────────────────────────────────────────────────────────────────────────

async def overview(address, lat, lon, pin, request: Request | None = None) -> dict:
    with _timing.collect() as timer:
        ok = False
        try:
            out = await _until_disconnected(request, _overview(address, lat, lon, pin))
            ok = True
            return _with_timings(out, timer)
        finally:
            _log("overview", ok, timer)


async def _overview(address, lat, lon, pin) -> dict:
    from backend import main
    from backend.retrieval.geo import community_area_by_point, community_area_name

    cand_task = await main._address_candidates(address, lat, lon, pin)
    with _timing.span("resolution"):
        # Shared with /api/scorecard/first, which the page starts at the same moment (Item 82 measured the
        # duplicate): one resolution for the pair.
        rl = await inflight.shared(("resolve", address, lat, lon, pin), lambda: main._resolve_location(address, lat, lon, pin))
    main._require_chicago(rl)
    ca = community_area_by_point(rl.lat, rl.lon)
    rec = Record(
        id=secrets.token_urlsafe(12), address_in=address, rl=rl, identity=None,
        ca=ca, ca_name=community_area_name(ca) if ca else None,
    )
    with _timing.span("fetch"):
        await _gather_into(rec, _overview_coros(rec))
    prop = rec.results.get("property")
    rec.identity = await main._reconcile_identity(address, rl, None if isinstance(prop, Exception) else prop)
    rec.cand_task, rec.cand_applies = cand_task, cand_task is not None
    await _take_candidates(rec, 0)  # only if already in: the Overview doesn't wait for the Sources panel
    rec.parts_in.add("overview")
    _records.set(rec.id, rec)
    return await _respond(rec, "overview", [])


async def part(name: str, lookup: str, have: str | None, request: Request | None = None) -> dict:
    if name not in LATE_PARTS:
        raise HTTPException(status_code=404, detail=f"No profile part named {name!r}.")
    claims = read_lookup(lookup)
    with _timing.collect() as timer:
        ok = False
        try:
            out = await _until_disconnected(request, _part(name, claims, have))
            ok = True
            return _with_timings(out, timer)
        finally:
            _log(name, ok, timer)


async def _part(name: str, claims: dict, have: str | None) -> dict:
    rec = _records.get(claims["i"])
    if rec is None:
        # The server lost this lookup (a restart or eviction): rebuild it from the token. The Overview's calls and
        # the parts the page already has are cached by now, so this is quick; then the asked part runs as usual.
        rec = _record_from_claims(claims)
        if rec.cand_applies and not (rec.ap_pins or rec.assessor_pins):
            from backend import main

            rec.cand_task = await main._address_candidates(rec.address_in, None, None, None)
        with _timing.span("rebuild"):
            await _gather_into(rec, _overview_coros(rec))
            rec.parts_in.add("overview")
            for p in [p for p in (have or "").split(",") if p in LATE_PARTS and p != name]:
                rec.timed_out[p] = await _run_late(rec, p, LATE_DEADLINE_S)
                rec.parts_in.add(p)
        _records.set(rec.id, rec)
    if name not in applicable_parts(rec):
        timed_out: list[str] = []
    else:
        timed_out = await _run_late(rec, name, LATE_DEADLINE_S)
    rec.timed_out[name] = timed_out
    rec.parts_in.add(name)
    await _take_candidates(rec, LATE_DEADLINE_S)  # started with the Overview: normally long since in
    return await _respond(rec, name, timed_out)


def _reset_for_tests() -> None:
    _records._store.clear()
    global _late_sem
    _late_sem = None
