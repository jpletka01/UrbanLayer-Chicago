"""Zoning rezonings Council has passed that the City's map doesn't show yet (WS1 M5).

A rezoning ordinance reaches the Zoning MapServer weeks or months after it passes (the 90th
percentile is about 114 days). In between, the Profile's district is the OLD one. This module
finds those ordinances and the parcels their titles list, so the Profile can say so.

**Daily, in the sync** (``build_rows``): the Clerk's passed ``ZONING RECLASSIFICATIONS`` of the
last 365 days; each is looked up on the map's layer 1 by record number (``CLERK_DOCNO``): no
polygon carries it → *off the map*. Its title is parsed (``address_titles``) and, for an
off-map ordinance, every listed address range is resolved to parcels (Address Points).

**Per parcel, on the request path, no network** (``matches_for``): the parcel's PIN is in an
off-map ordinance's parcel set, and the parcel's live map record doesn't already carry that
ordinance. A parcel whose PIN is unresolved is matched on the parsed address instead.

What this says, and does not: "a rezoning *listing this address* passed on <date>". An
ordinance's legal description can name part of a range, so we never say the parcel *was*
rezoned, and never say what it was rezoned to (reading the ordinance is WS1 M6).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from backend.legislation import address_titles, currency, ordinance_reader
from backend.legislation.address_titles import PARSER_VERSION, STREET_TYPES, parse_title
from backend.retrieval import clerk
from backend.retrieval.property import address_points

log = logging.getLogger(__name__)

LOOKBACK_DAYS = 365
OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "rezoning_overrides.json"
_MAP_BATCH = 40
_RESOLVE_CONCURRENCY = 4


class MapCheckUnavailable(Exception):
    """The zoning MapServer could not say which ordinances it carries. Never "all off the map"."""


# --- reviewed overrides ------------------------------------------------------------------------

def load_overrides(path: Path | None = None) -> dict[str, dict]:
    """``{record: {"segments": [...]} or {"pins": [...]}, "note": str}`` for titles the parser can't
    read. Hand-mapped by the monthly routine; an unreadable file is empty (and logged), never fatal."""
    path = path or OVERRIDES_PATH
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.error("rezoning overrides unreadable (%s): %s", path, exc)
        return {}
    rows = data.get("overrides") if isinstance(data, dict) else None
    return {k: v for k, v in (rows or {}).items() if isinstance(v, dict)}


# --- the map ----------------------------------------------------------------------------------

async def records_on_map(records: list[str], *, client=None) -> set[str]:
    """The subset of ``records`` that at least one layer-1 polygon carries as ``CLERK_DOCNO``.
    Raises ``MapCheckUnavailable`` on any failure: an unreachable map is not "off the map"."""
    from backend.retrieval import zoning

    client = client or zoning._get_arcgis_client()
    found: set[str] = set()
    for i in range(0, len(records), _MAP_BATCH):
        chunk = records[i:i + _MAP_BATCH]
        ids = ",".join(clerk.odata_str(r) for r in chunk)
        params = {
            "where": f"CLERK_DOCNO IN ({ids})", "outFields": "CLERK_DOCNO", "returnGeometry": "false",
            "returnDistinctValues": "true", "f": "json",
        }
        try:
            resp = await client.post(zoning.ZONING_QUERY_URL, data=params, timeout=60)
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            raise MapCheckUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if not isinstance(body, dict) or "error" in body or "features" not in body:
            raise MapCheckUnavailable(f"unexpected MapServer reply: {str(body)[:200]}")
        found |= {f["attributes"]["CLERK_DOCNO"] for f in body["features"] if f.get("attributes", {}).get("CLERK_DOCNO")}
    return found


# --- resolving a title to parcels ---------------------------------------------------------------

async def resolve_segment(seg: dict, *, client=None) -> list[dict]:
    typ = seg.get("type") or ""
    return await address_points.pins_in_range(
        direction=seg["dir"], names=address_titles.name_candidates(seg["name"]),
        types=[t for t in (typ, STREET_TYPES.get(typ)) if t], lo=seg["lo"], hi=seg["hi"],
        side=seg.get("side", "both"), client=client,
    )


async def resolve_pins(segments: list[dict], *, client=None) -> tuple[list[list], list[str]]:
    """``(pins, unresolved)``: ``pins`` = ``[[pin, lat, lon], …]`` over every segment, ``unresolved``
    = the segments (as written) that matched no address point."""
    sem = asyncio.Semaphore(_RESOLVE_CONCURRENCY)

    async def one(seg):
        async with sem:
            return await resolve_segment(seg, client=client)

    results = await asyncio.gather(*(one(s) for s in segments))
    pins: dict[str, list] = {}
    unresolved: list[str] = []
    for seg, rows in zip(segments, results):
        if not rows:
            unresolved.append(f"{seg['raw']} {seg['dir']} {seg['name']} {seg.get('type') or ''}".strip())
        for r in rows:
            pins.setdefault(r["pin"], [r["pin"], r["lat"], r["lon"]])
    return sorted(pins.values()), unresolved


# --- the daily build ----------------------------------------------------------------------------

def _base_row(m: clerk.ClerkMatter) -> dict:
    return {
        "record": m.record_number, "matter_id": m.matter_id, "url": m.url, "passed_on": m.passed_on.isoformat(),
        "substitute": m.is_substitute, "title": m.title,
    }


def _parse_for(row: dict, overrides: dict[str, dict]) -> tuple[dict, str]:
    """``(parse, source)`` for one title, applying a reviewed override."""
    parsed = parse_title(row["title"])
    ov = overrides.get(row["record"])
    if ov and ov.get("segments"):
        return {"status": "clean", "segments": list(ov["segments"]), "notes": [], "maps": parsed.maps, "app_no": parsed.app_no}, "override"
    return {"status": parsed.status, "segments": [s.as_dict() for s in parsed.segments], "notes": parsed.notes,
            "maps": parsed.maps, "app_no": parsed.app_no}, "parsed"


async def build_rows(
    matters: list[clerk.ClerkMatter], previous: list[dict] | None = None, *, client=None, map_client=None,
    overrides: dict[str, dict] | None = None, resolve_on_map: bool = False,
) -> list[dict]:
    """The snapshot's ``rezonings`` rows for these passed matters.

    Parsing and parcel resolution are reused from ``previous`` unless the parser version changed
    or the record is new; the map check runs every time. ``resolve_on_map`` also resolves parcels
    for ordinances already on the map (the backtest harness; the daily sync never needs them).
    Raises ``MapCheckUnavailable`` when the map can't be checked.
    """
    overrides = load_overrides() if overrides is None else overrides
    prev = {r["record"]: r for r in previous or [] if r.get("parser") == PARSER_VERSION}
    on_map = await records_on_map([m.record_number for m in matters], client=map_client)

    rows: list[dict] = []
    for m in sorted(matters, key=lambda m: (m.passed_on, m.record_number)):
        row = _base_row(m)
        row["map_status"] = "on_map" if m.record_number in on_map else "off_map"
        old = prev.get(m.record_number)
        if old and old.get("parse") and (old.get("pins") is not None or row["map_status"] == "on_map" and not resolve_on_map):
            row.update({k: old.get(k) for k in ("parse", "parser", "pins", "unresolved", "source")})
        else:
            row["parse"], row["source"] = _parse_for(row, overrides)
            row["parser"] = PARSER_VERSION
            row["pins"], row["unresolved"] = None, []
        if row["pins"] is None and row["parse"]["status"] == "clean" and (row["map_status"] == "off_map" or resolve_on_map):
            row["pins"], row["unresolved"] = await resolve_pins(row["parse"]["segments"], client=client)
        rows.append(row)
    return rows


def summary(rows: list[dict]) -> dict:
    """Counts for the sync log and the admin card."""
    off = [r for r in rows if r.get("map_status") == "off_map"]
    return {
        "passed": len(rows),
        "off_map": len(off),
        "off_map_oldest_days": max(((date.today() - date.fromisoformat(r["passed_on"])).days for r in off), default=None),
        "flaggable": sum(1 for r in off if is_flaggable(r)),
        "with_parcels": sum(1 for r in off if is_flaggable(r) and r.get("pins")),
        "unparsed": [r["record"] for r in off if r["parse"]["status"] != "clean"],
        "no_parcels": [r["record"] for r in off if r["parse"]["status"] == "clean" and not r.get("pins")],
    }


# --- per parcel (request path) -------------------------------------------------------------------

def is_flaggable(row: dict, today: date | None = None) -> bool:
    """An off-map ordinance we can place: a clean (or reviewed) parse, passed within the lookback."""
    if row.get("map_status") != "off_map" or (row.get("parse") or {}).get("status") != "clean":
        return False
    try:
        age = ((today or date.today()) - date.fromisoformat(row["passed_on"])).days
    except (KeyError, ValueError):
        return False
    return 0 <= age <= LOOKBACK_DAYS


def _segment_matches(seg: dict, number: int, direction: str, name: str, address: str | None) -> bool:
    if seg["dir"] != direction or name not in address_titles.name_candidates(seg["name"]):
        return False
    if not seg["lo"] <= number <= seg["hi"]:
        return False
    if seg.get("side") == "odd" and number % 2 == 0 or seg.get("side") == "even" and number % 2 == 1:
        return False
    return not currency.suffix_conflicts(seg.get("type"), address)


def matches_for(
    pin: str | None, address: str | None, live_ordinance: str | None, snapshot: dict | None = None,
    today: date | None = None, live_district: str | None = None,
) -> list[dict]:
    """The off-map rezonings that list this parcel, newest first. Empty unless the snapshot is
    usable (not failed/suspect, checked within 14 days): a stale list could name an ordinance
    that has reached the map since."""
    snapshot = snapshot if snapshot is not None else currency.load_snapshot()
    if not snapshot or currency.check_state(snapshot) == "unknown" or snapshot.get("status") == "failed":
        return []
    parts = currency.address_parts(address)
    out: list[dict] = []
    for row in snapshot.get("rezonings") or []:
        if not is_flaggable(row, today) or row["record"] == (live_ordinance or ""):
            continue
        hit = None
        if pin and any(p[0] == pin for p in row.get("pins") or []):
            hit, by = _describe(row, address), "pin"
        elif not pin and parts:
            number, direction, name = parts
            seg = next((s for s in row["parse"]["segments"] if _segment_matches(s, number, direction, name, address)), None)
            if seg:
                hit, by = _describe(row, address, seg), "address"
        if hit:
            hit = {**hit, "matched_by": by}
            # WS1 M6: the AI-read new district, only when the sync validated it against the live map
            # (and, for a multi-change ordinance, only the change that starts from this parcel's district).
            if (d := ordinance_reader.district_for(row, live_district)):
                hit.update(d, agreement=(snapshot.get("rezoning_check") or {}).get("agreement") or {"n": 0, "agree": 0})
            out.append(hit)
    return sorted(out, key=lambda r: r["passed_on"], reverse=True)


def _describe(row: dict, address: str | None, seg: dict | None = None) -> dict:
    """The row as the Profile shows it. ``segment`` is the listing's own words for the range that
    reaches this parcel (the parcel's own range when we matched on the address)."""
    parts = currency.address_parts(address)
    if seg is None and parts:
        number, direction, name = parts
        seg = next((s for s in row["parse"]["segments"] if _segment_matches(s, number, direction, name, address)), None)
    seg = seg or (row["parse"]["segments"] or [None])[0]
    text = None
    if seg:
        rng = str(seg["lo"]) if seg["lo"] == seg["hi"] else f"{seg['lo']}-{seg['hi']}"
        text = f"{rng} {seg['dir']} {seg['name'].title()} {(seg.get('type') or '').title()}".strip()
    return {
        "record": row["record"], "passed_on": row["passed_on"], "url": row["url"], "segment": text,
        "maps": row["parse"].get("maps") if isinstance(row["parse"], dict) else None,
    }
