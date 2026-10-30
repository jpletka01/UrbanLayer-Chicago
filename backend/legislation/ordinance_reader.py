"""Read the new district out of a passed rezoning ordinance (WS1 M6, AI-read, labeled).

``rezonings`` says a rezoning *listing this address* passed but isn't on the City map. This module
says what it changes: for each off-map ordinance, the Legislation PDF that passed goes to Claude as
a document block and comes back as ``[{map_no, from_district, to_district}]``.

An AI reading is shown only when a deterministic check agrees: the ``from_district`` must be the
district the live map shows at one or more of the ordinance's parcels. Otherwise the row says
"district not read" and the Profile keeps the link only. A failed read (PDF unreachable, model
error, unparseable reply) is recorded as ``failed`` and retried on the next run; it is never stored
as "this ordinance has no district".

Dormant until ``ordinance_reader_enabled`` is set and an API key exists (the first live run is a
production event). Nothing here runs on the request path.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone

from backend.config import get_settings
from backend.retrieval import clerk

log = logging.getLogger(__name__)

READER_VERSION = 1
MAX_PDF_BYTES = 8_000_000
_PAUSE_S = 1.0          # be polite to the City Clerk
_LIVE_POINTS = 3        # parcels whose live district validates a reading

# A Chicago zone class: B2-5, RS-3, RM-4.5, DX-12, DC-16, POS-1, plus PD/PMD numbers and the T district.
_DISTRICT_RE = re.compile(r"^(?:[A-Z]{1,4}\d?-\d{1,2}(?:\.\d)?|(?:PD|PMD)\s?\d+[A-Z]?|T)$")

PROMPT = (
    "This is a City of Chicago zoning reclassification ordinance. Reply with JSON only, no prose: "
    '{"common_address": <string or null>, "changes": [{"map_no": <string or null>, '
    '"from_district": <zone class being replaced, e.g. "C2-2">, "to_district": <zone class it becomes, '
    'e.g. "B2-5">}]}. Write each zone class in its standard hyphenated form (the ordinance may print "RT4" or "RM 4.5"; give "RT-4", "RM-4.5"). '
    "One entry per map amendment in the ordinance. If you cannot read a value, use null; never guess."
)


class ReaderUnavailable(Exception):
    """The PDF or the model could not be reached or understood. Retried next run, never cached."""


def normalize_district(value) -> str | None:
    """``"c2-2"`` → ``"C2-2"``; anything that isn't a zone class → None."""
    if not isinstance(value, str):
        return None
    v = re.sub(r"\s+", " ", value.strip().upper().replace("–", "-").replace("—", "-"))
    # Ordinances write "RT4", "RM 4.5", "RM- 4.5" for the residential classes; the map says "RT-4", "RM-4.5".
    v = re.sub(r"^(RS|RT|RM)\s*-?\s*(\d(?:\.\d)?)$", r"\1-\2", v)
    return v if _DISTRICT_RE.match(v) else None


def parse_reply(text: str) -> dict:
    """The model's JSON → ``{"common_address", "changes": [{map_no, from_district, to_district}]}``
    with districts normalized (None when malformed). Raises ``ReaderUnavailable`` on a reply that
    isn't the expected object."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ReaderUnavailable("reply has no JSON object")
    try:
        body = json.loads(m.group(0))
    except ValueError as exc:
        raise ReaderUnavailable(f"reply JSON invalid: {exc}") from exc
    changes = body.get("changes") if isinstance(body, dict) else None
    if not isinstance(changes, list):
        raise ReaderUnavailable("reply has no 'changes' list")
    out = []
    for c in changes:
        if not isinstance(c, dict):
            continue
        out.append({
            "map_no": str(c["map_no"]).strip() if c.get("map_no") else None,
            "from_district": normalize_district(c.get("from_district")),
            "to_district": normalize_district(c.get("to_district")),
        })
    addr = body.get("common_address")
    return {"common_address": addr.strip() if isinstance(addr, str) else None, "changes": out}


async def fetch_pdf(matter: clerk.ClerkMatter, *, client=None) -> bytes:
    """The Legislation PDF that passed (the SO Final for a substitute, never the EDS)."""
    att = matter.legislation_pdf()
    if att is None or not att.url:
        raise ReaderUnavailable(f"{matter.record_number}: no Legislation PDF")
    client = client or clerk._get_client()
    try:
        resp = await client.get(att.url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        raise ReaderUnavailable(f"{matter.record_number}: PDF fetch failed: {type(exc).__name__}: {exc}") from exc
    if len(resp.content) > MAX_PDF_BYTES or not resp.content.startswith(b"%PDF"):
        raise ReaderUnavailable(f"{matter.record_number}: PDF unusable ({len(resp.content)} bytes)")
    return resp.content


async def read_ordinance(pdf: bytes, *, client=None, model: str | None = None) -> dict:
    """Ask the model what the PDF changes. ``client`` is an ``AsyncAnthropic`` (a fake in tests)."""
    if client is None:
        from backend.llm import get_anthropic_client

        client = get_anthropic_client()
    model = model or get_settings().ordinance_reader_model
    try:
        msg = await client.messages.create(
            model=model, max_tokens=600,
            messages=[{"role": "user", "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                "data": base64.b64encode(pdf).decode()}},
                {"type": "text", "text": PROMPT},
            ]}],
        )
    except Exception as exc:
        raise ReaderUnavailable(f"model call failed: {type(exc).__name__}: {exc}") from exc
    text = "".join(getattr(b, "text", "") for b in msg.content)
    return {**parse_reply(text), "model": model}


def validate(reading: dict, live_districts: set[str]) -> dict:
    """Keep the changes whose from/to are zone classes and whose ``from_district`` is a district the
    live map shows at the ordinance's parcels. Returns ``{"status": "validated"|"unvalidated", "changes"}``."""
    live = {d.upper() for d in live_districts if d}
    kept = [c for c in reading.get("changes") or []
            if c.get("from_district") and c.get("to_district") and c["from_district"] in live]
    return {"status": "validated" if kept else "unvalidated", "changes": kept}


async def live_districts_for(pins: list[list], *, lookup=None) -> set[str]:
    """The live map's districts at up to ``_LIVE_POINTS`` of the ordinance's parcels (``[pin, lat, lon]``)."""
    from backend.retrieval import zoning

    lookup = lookup or zoning.lookup_zoning
    out: set[str] = set()
    for _pin, lat, lon in (pins or [])[:_LIVE_POINTS]:
        try:
            z = await lookup(lat, lon)
        except Exception as exc:  # a map hiccup leaves the reading unvalidated, not wrong
            log.warning("live district lookup failed at %s,%s: %s", lat, lon, exc)
            continue
        if z and z.get("zone_class"):
            out.add(str(z["zone_class"]).upper())
    return out


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reusable(old: dict | None) -> bool:
    """A previous reading we need not redo: same reader version and it actually read the PDF."""
    return bool(old) and old.get("reader") == READER_VERSION and old.get("status") in ("validated", "unvalidated", "read") \
        and old.get("raw") is not None


async def attach_readings(
    rows: list[dict], matters: dict[str, clerk.ClerkMatter], previous: list[dict] | None, *,
    pdf_client=None, model_client=None, lookup=None, pause: float = _PAUSE_S,
) -> int:
    """Set ``row["ai_reading"]`` on each flaggable off-map row that has parcels. Returns the number
    of model calls made. Stored raw readings are re-validated against the live map without a new
    call; failures are recorded and retried next run."""
    prev = {r["record"]: r.get("ai_reading") for r in previous or []}
    calls = 0
    for row in rows:
        if row.get("map_status") != "off_map" or not row.get("pins") or (row.get("parse") or {}).get("status") != "clean":
            continue
        old = prev.get(row["record"])
        reading = old if reusable(old) else None
        if reading is None:
            matter = matters.get(row["record"])
            try:
                if matter is None:
                    raise ReaderUnavailable("matter not in this run")
                if calls:
                    await asyncio.sleep(pause)
                raw = await read_ordinance(await fetch_pdf(matter, client=pdf_client), client=model_client)
                calls += 1
            except ReaderUnavailable as exc:
                row["ai_reading"] = {"status": "failed", "reader": READER_VERSION, "error": str(exc)[:200], "attempted_at": _now()}
                continue
            reading = {"reader": READER_VERSION, "raw": {"common_address": raw["common_address"], "changes": raw["changes"]},
                       "model": raw["model"], "read_at": _now(), "pdf": (matter.legislation_pdf().url if matter.legislation_pdf() else None)}
        live = await live_districts_for(row["pins"], lookup=lookup)
        v = validate(reading["raw"], live)
        row["ai_reading"] = {**{k: reading[k] for k in ("reader", "raw", "model", "read_at", "pdf") if k in reading}, **v,
                             "live_districts": sorted(live)}
    return calls


async def map_districts_now(previous_rows: list[dict], rows: list[dict], *, lookup=None) -> dict[str, set[str]]:
    """For each ordinance that was off the map with a validated reading and is on it now, the districts
    the map shows at its parcels (``{record: {district}}``)."""
    now_on = {r["record"] for r in rows if r.get("map_status") == "on_map"}
    out: dict[str, set[str]] = {}
    for old in previous_rows or []:
        if old.get("record") in now_on and old.get("map_status") == "off_map" and (old.get("ai_reading") or {}).get("status") == "validated":
            out[old["record"]] = await live_districts_for(old.get("pins") or [], lookup=lookup)
    return out


def agreement_update(previous_rows: list[dict], rows: list[dict], map_districts: dict[str, set[str]], log_so_far: list[dict] | None) -> list[dict]:
    """Append ``{record, to_district, map_district, agree}`` for each ordinance that was off the map
    with a validated reading and is on it now. ``map_districts`` = {record: districts the map shows at its
    parcels now}. Each record is logged once."""
    log_ = list(log_so_far or [])
    seen = {e["record"] for e in log_}
    now_on = {r["record"] for r in rows if r.get("map_status") == "on_map"}
    for old in previous_rows or []:
        rec, rd = old.get("record"), old.get("ai_reading") or {}
        if rec in seen or rec not in now_on or old.get("map_status") != "off_map" or rd.get("status") != "validated":
            continue
        shown = {d.upper() for d in map_districts.get(rec, set())}
        if not shown:
            continue  # couldn't see the map there: neither agree nor disagree
        tos = {c["to_district"] for c in rd["changes"]}
        log_.append({"record": rec, "to_district": sorted(tos), "map_district": sorted(shown), "agree": bool(tos & shown),
                     "logged_at": _now()})
    return log_


def agreement_counts(log_: list[dict] | None) -> dict:
    log_ = log_ or []
    return {"n": len(log_), "agree": sum(1 for e in log_ if e.get("agree"))}


def district_for(row: dict, live_district: str | None = None) -> dict | None:
    """What the Profile may say about the new district for one ordinance, or None. A multi-change
    ordinance is narrowed by the parcel's own live district; ambiguity yields None."""
    rd = row.get("ai_reading") or {}
    if rd.get("status") != "validated":
        return None
    changes = rd.get("changes") or []
    if live_district:
        changes = [c for c in changes if c["from_district"] == live_district.upper()]
    tos = {(c["from_district"], c["to_district"]) for c in changes if c["from_district"] != c["to_district"]}  # "RT-4 to RT-4" is no change
    if len(tos) != 1:
        return None
    frm, to = next(iter(tos))
    return {"from_district": frm, "to_district": to, "district_source": "ai_read_ordinance", "pdf": rd.get("pdf")}
