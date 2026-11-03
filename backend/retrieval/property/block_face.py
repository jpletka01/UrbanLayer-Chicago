"""The RS-3 "60% of the block face" test (§17-2-0303-B.1; WS5 PR4, decision Item 67).

§17-2-0303-B.1 lets an RS-3 two-unit building use 1,500 sq ft of lot per unit "when 60% or more of the zoning
lots fronting on the same side of the street between the two nearest intersecting streets have been lawfully
improved with buildings containing more than one dwelling unit" (the 606 district is the other trigger, Item 42).
§17-17-0221 defines a block face the same way: all lots abutting one side of a street between the two nearest
intersecting streets.

How we read it, from official records only (no model):

1. **The block face** comes from the City's street centerlines (``pr57-gg9e``): each segment carries its address
   range per side and the street it meets at each end (``f_cross_st`` / ``t_cross_st``; ``0`` = no street, e.g. a
   bend or a dead end). Segments of the subject's street are chained end to end until each end meets a real
   intersecting street. The face is that span's address range on the subject's side (by parity). Item 44's
   hundred-block stand-in is gone.
2. **The lots** are every base parcel (PIN10) on that side with its own Assessor address in the range, in *any*
   district: the code counts "the zoning lots fronting" the face, not only RS-3 ones (Item 44 counted only RS-3).
   A PIN10 stands in for a zoning lot (a zoning lot can span several PINs; we can't see that).
3. **Units per lot**: the Discovery index's ``units`` (Item 59) when it has it, else the Assessor's residential
   characteristics (``x54s-btds``, newest year), decoded by Item 44's rules: "Two".."Six" = that many; "None" on a
   single-card parcel = one dwelling; a second card = unknown; no row: a condo building (2-99, or unit PINs on the
   PIN10) or 3-xx = two or more, 1-xx = vacant, anything else unknown.
4. **The gate** (Jack, 2026-10-31): a face is judged only when at least 90% of its lots have a count and it has
   at least four lots; then the rule is met at 60% or more with two or more units. Unknown lots count as *not*
   two-plus, so "met" is never overstated. "Lawfully improved" is not something a record shows: we say so.

A failed source raises ``BlockFaceError`` and nothing is cached: the unit yield then says the test wasn't checked.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from typing import Any

import httpx

from backend.config import get_settings
from backend.models import BlockFaceTest
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

COVERAGE_GATE = 0.90
RULE_SHARE = 0.60
MIN_LOTS = 4
DATASET_CENTERLINES = "pr57-gg9e"
_PIN_BATCH = 300

_segments_cache = TTLCache(ttl_seconds=7 * 86400, maxsize=512, name="street_centerlines")
_result_cache = TTLCache(ttl_seconds=86400, maxsize=512, name="block_face")

_APT_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6}
_STREET_TYPES = {"AVE", "ST", "BLVD", "DR", "PL", "CT", "RD", "PKWY", "TER", "LN", "WAY", "HWY", "SQ", "CIR", "ROW", "PLZ"}
_ADDRESS = re.compile(r"^\s*(\d+)\s+([NSEW])\s+(.+?)\s*(?:,.*)?$")


class BlockFaceError(RuntimeError):
    """A source the test needs didn't answer: "not checked", never "not met"."""


def split_address(address: str | None) -> tuple[int, str, str, str | None] | None:
    """(1747, "N", "KEDZIE", "AVE") for "1747 N KEDZIE AVE"; None for an approximate or unparsable address."""
    if not address or address.lstrip().startswith("~"):
        return None
    m = _ADDRESS.match(address.upper())
    if not m:
        return None
    words = m.group(3).split()
    street_type = words[-1] if len(words) > 1 and words[-1] in _STREET_TYPES else None
    name = " ".join(words[:-1] if street_type else words)
    return int(m.group(1)), m.group(2), name, street_type


def _num(v: Any) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def face_range(segments: list[dict], number: int) -> tuple[int, int, str, str] | None:
    """(lo, hi, from_street, to_street) of the block face holding ``number`` on its side of the street.

    Segments are chained through their end nodes (``fnode_id`` / ``tnode_id``) until the node meets a real
    intersecting street (``*_cross_st`` other than 0). None when no segment carries the number.
    """
    parity = number % 2

    def side(seg: dict) -> tuple[int, int] | None:
        for f, t in (("l_f_add", "l_t_add"), ("r_f_add", "r_t_add")):
            lo, hi = _num(seg.get(f)), _num(seg.get(t))
            if lo and hi and lo % 2 == parity:
                return min(lo, hi), max(lo, hi)
        return None

    home = next((s for s in segments if (r := side(s)) and r[0] <= number <= r[1]), None)
    if home is None:
        return None
    by_node: dict[Any, list[dict]] = defaultdict(list)
    for s in segments:
        by_node[s.get("fnode_id")].append(s)
        by_node[s.get("tnode_id")].append(s)

    def cross_at(seg: dict, node: Any) -> str | None:
        """The street ``seg`` meets at ``node``, or None when that node meets no street (a bend, an alley)."""
        end = "f" if seg.get("fnode_id") == node else "t"
        if str(seg.get(f"{end}_cross_st") or "0") == "0":
            return None
        parts = str(seg.get(f"{end}_cross") or "").split("|")
        return " ".join(p for p in parts[1:4] if p).strip() or "a cross street"

    lo, hi = side(home)
    seen = {id(home)}
    ends: dict[str, str] = {}
    # Walk out from each end of the home segment, through nodes that meet no street, whichever way each
    # segment happens to be digitized.
    for label, start in (("f", home.get("fnode_id")), ("t", home.get("tnode_id"))):
        seg, node = home, start
        while (street := cross_at(seg, node)) is None:
            nxt = next((s for s in by_node.get(node, []) if id(s) not in seen and side(s)), None)
            if nxt is None:
                street = "the end of the street"
                break
            seen.add(id(nxt))
            seg = nxt
            node = nxt.get("tnode_id") if nxt.get("fnode_id") == node else nxt.get("fnode_id")
            r = side(seg)
            lo, hi = min(lo, r[0]), max(hi, r[1])
        ends[label] = street
    return lo, hi, ends["f"], ends["t"]


async def _street_segments(direction: str, name: str, street_type: str | None, *, client) -> list[dict]:
    key = f"{direction}:{name}:{street_type or ''}"
    cached = _segments_cache.get(key)
    if cached is not None:
        return cached
    where = f"pre_dir='{direction}' AND street_nam='{name.replace(chr(39), chr(39) * 2)}'"
    if street_type:
        where += f" AND street_typ='{street_type}'"
    try:
        rows = await socrata_get(DATASET_CENTERLINES, {
            "$select": "fnode_id,tnode_id,l_f_add,l_t_add,r_f_add,r_t_add,f_cross,f_cross_st,t_cross,t_cross_st",
            "$where": where, "$limit": 5000,
        }, client=client)
    except Exception as exc:
        raise BlockFaceError(f"street centerlines didn't answer: {exc}") from exc
    if not rows:
        raise BlockFaceError(f"no centerline segments for {direction} {name} {street_type or ''}".strip())
    _segments_cache.set(key, rows)
    return rows


def _face_lots(direction: str, name: str, street_type: str | None, lo: int, hi: int, parity: int) -> dict[str, dict]:
    """PIN10 -> {"pins": [...], "class": ..., "units": ...} for every base parcel with its own address on the face."""
    from backend.discovery import parcel_source

    try:
        version = parcel_source.current_version()
    except RuntimeError as exc:
        raise BlockFaceError("the Discovery index is not loaded") from exc
    if version == parcel_source.EMPTY_VERSION:
        raise BlockFaceError("the Discovery index is empty")  # no lots to list: not checked, never "no lots"
    lots: dict[str, dict] = {}
    for p in street_index(version).get((direction, name, street_type), []):
        number, pin, attrs = p
        if lo <= number <= hi and number % 2 == parity:
            pin10 = pin.replace("-", "")[:10]
            lot = lots.setdefault(pin10, {"pins": [], "class": None, "units": None, "condo": False})
            lot["pins"].append(pin.replace("-", ""))
            if not pin.replace("-", "").endswith("0000"):
                lot["condo"] = True  # unit PINs on the PIN10: a condominium building
            if pin.replace("-", "").endswith("0000") or lot["class"] is None:
                lot["class"] = attrs.get("class")
                lot["units"] = attrs.get("units") if isinstance(attrs.get("units"), int) else lot["units"]
    return lots


_street_index: dict | None = None
_street_index_version: str | None = None


def street_index(version: str) -> dict:
    """(direction, name, type) -> [(number, pin, attrs)] over the Discovery index, built once per dataVersion."""
    global _street_index, _street_index_version
    if _street_index is None or _street_index_version != version:
        from backend.discovery.parcel import default_source

        out: dict = defaultdict(list)
        for p in default_source.get(version):
            parts = split_address(p.get("address"))
            if parts:
                number, direction, name, street_type = parts
                out[(direction, name, street_type)].append((number, p.pin, p._attrs))
        _street_index, _street_index_version = dict(out), version
    return _street_index


def units_from_record(cls: str | None, chars: dict | None, *, condo: bool = False) -> int | None:
    """Dwelling units from the Assessor's record (Item 44's rules); 2 means "two or more" from a class."""
    c = (cls or "").replace("-", "")
    if condo or c == "299" or c.startswith("3"):
        return 2
    if chars is not None:
        apts = (chars.get("char_apts") or "").strip()
        if apts in _APT_WORDS:
            return _APT_WORDS[apts]
        if apts == "None":
            return 1 if (_num(chars.get("pin_num_cards")) or 1) <= 1 else None
        return None
    if c.startswith("1"):
        return 0
    return None


async def _characteristics(pins: list[str], *, client) -> dict[str, dict]:
    settings = get_settings()
    out: dict[str, dict] = {}
    for i in range(0, len(pins), _PIN_BATCH):
        chunk = pins[i:i + _PIN_BATCH]
        try:
            rows = await socrata_get(settings.dataset_ccao_characteristics, {
                "$select": "pin,year,char_apts,pin_num_cards", "$where": f"pin in ({','.join(repr(p) for p in chunk)})",
                "$order": "year DESC", "$limit": 50000,
            }, client=client, base_url=settings.cook_county_socrata_base,
                app_token=settings.cook_county_socrata_token or None)
        except Exception as exc:
            raise BlockFaceError(f"Assessor characteristics didn't answer: {exc}") from exc
        for row in rows:
            out.setdefault(str(row.get("pin")), row)  # year DESC: the first row per PIN is the newest
    return out


def judge(units: list[int | None]) -> tuple[str, int, int]:
    """(state, lots with a count, lots with two or more units) for a face's lots."""
    n = len(units)
    known = [u for u in units if u is not None]
    two_plus = sum(1 for u in known if u >= 2)
    if n < MIN_LOTS or len(known) / n < COVERAGE_GATE:
        return "not_computable", len(known), two_plus
    return ("met" if two_plus / n >= RULE_SHARE else "not_met"), len(known), two_plus


async def block_face_test(address: str, *, client: httpx.AsyncClient | None = None) -> BlockFaceTest:
    """The §17-2-0303-B.1 block-face test for the parcel at ``address`` (an RS-3 parcel's own address)."""
    parts = split_address(address)
    if parts is None:
        return BlockFaceTest(state="not_computable", reason="address")
    number, direction, name, street_type = parts
    key = f"{number}:{direction}:{name}:{street_type or ''}"
    cached = _result_cache.get(key)
    if cached is not None:
        return cached

    segments = await _street_segments(direction, name, street_type, client=client)
    span = face_range(segments, number)
    if span is None:
        return BlockFaceTest(state="not_computable", reason="no_segment")
    lo, hi, from_street, to_street = span
    # The first call per index version builds the street index (one pass over the index): off the event loop.
    lots = await asyncio.to_thread(_face_lots, direction, name, street_type, lo, hi, number % 2)
    need = sorted(p for lot in lots.values() if lot["units"] is None and not lot["condo"] for p in lot["pins"][:1])
    chars = await _characteristics(need, client=client) if need else {}
    units = [
        lot["units"] if lot["units"] is not None
        else units_from_record(lot["class"], chars.get(lot["pins"][0]), condo=lot["condo"])
        for lot in lots.values()
    ]
    state, known, two_plus = judge(units)
    side = "odd" if number % 2 else "even"
    result = BlockFaceTest(
        state=state, lots=len(units), counted=known, two_plus=two_plus,
        street=f"{direction} {name}{' ' + street_type if street_type else ''}", side=side,
        from_number=lo, to_number=hi, from_street=from_street, to_street=to_street,
        reason="coverage" if state == "not_computable" else None,
    )
    _result_cache.set(key, result)
    return result
