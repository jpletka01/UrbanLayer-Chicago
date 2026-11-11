"""The Assessor's own address for a Discovery lot with no Address Point, checked before use (decision Item 109).

A lot with no City/County Address Point used to show the nearest point's address with a ``~`` prefix. That address is,
by construction, another parcel's: "~2624 S Troy" (16-25-300-030) is the house next door to the empty lot, so the card
and Street View led to the wrong building. The Cook County Assessor gives every PIN a property address
(``3723-97qp``, ``prop_address_full``), but it carries placeholders too (unit tails like "2 FL", one building's address
on several PINs, an institution's mailing address on its outlying lots), so it is shown only when it lands on this lot:

1. it parses as ``<number> <N|S|E|W> <street>`` (a unit tail is dropped: the building's street address is shown);
2. the nearest block face of that street (the City's street centerlines, ``pr57-gg9e``) lies within
   ``MAX_STREET_FT`` of the lot, and its side facing the lot has the number's parity and holds it in its range;
3. the number is within ``TOLERANCE_NUMBERS`` of the number the lot's position along that block face implies
   (linear interpolation; calibrated on 583 lots with their own Address Point: median error 1.8, p95 4.8);
4. if the address is an Address Point somewhere, one of its points lies within ``AP_ELSEWHERE_FT`` of the lot (else it
   is another building's address).

A lot that fails keeps its ``~`` nearest address: the prefix still means "approximate". Pure functions over the local
copy written by ``lot_sources`` (tables ``assessor_address``, ``address_points``, ``centerlines``); no network.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import shapely
from shapely.strtree import STRtree

TOLERANCE_NUMBERS = 6.0
MAX_STREET_FT = 250.0
AP_ELSEWHERE_FT = 60.0

_FT_PER_DEG_LAT = 364_000.0
_FT_PER_DEG_LON = _FT_PER_DEG_LAT * 0.7447  # cos(41.84°), as lot_facts

# The centerlines' street types (pr57-gg9e ``street_typ``), plus the Assessor's spellings that differ.
STREET_TYPES = frozenset({
    "AVE", "ST", "PL", "EXPY", "DR", "RD", "BLVD", "ER", "XR", "PKWY", "CT", "TER", "RL", "HWY", "SR", "LN", "PLZ",
    "WAY", "SQ", "TOLL", "CRES", "ROW", "ORD", "PKY", "CIR",
})
_TYPE_ALIAS = {"PKY": "PKWY"}
# The Assessor's street spellings that differ from the City's (measured 2026-11-11 over every Chicago base PIN).
_NAME_ALIAS = {
    "LASALLE": "LA SALLE",
    "KING": "DR MARTIN LUTHER KING JR",
    "MARTIN LUTHER KING": "DR MARTIN LUTHER KING JR",
    "DR MARTIN LUTHER KING": "DR MARTIN LUTHER KING JR",
    "SOUTH PARK": "DR MARTIN LUTHER KING JR",  # South Park Way, renamed King Drive in 1968
}


@dataclass(frozen=True)
class Parsed:
    number: int
    predir: str
    name: str
    typ: str | None
    unit: str

    @property
    def street(self) -> tuple[str, str, str | None]:
        return (self.predir, self.name, self.typ)

    @property
    def base(self) -> str:
        """The street address without its unit tail, spelled as Address Points' ``cmpaddabrv``."""
        return " ".join([str(self.number), self.predir, self.name] + ([self.typ] if self.typ else []))


def parse(address: str | None) -> Parsed | None:
    """``"2626 S TROY ST"`` -> Parsed; ``None`` for a placeholder with no number or direction ("W TILDEN AVE",
    "1538 RAILROAD", "UNKNOWN") or a number 0."""
    if not address:
        return None
    t = address.upper().split()
    if len(t) < 3 or not t[0].isdigit() or int(t[0]) <= 0 or t[1] not in ("N", "S", "E", "W"):
        return None
    rest = t[2:]
    # The last street-type token after the first word ends the street; what follows it is a unit ("2 FL", "REAR").
    ti = max((i for i, x in enumerate(rest) if x in STREET_TYPES and i > 0), default=None)
    if ti is None:  # "AVENUE E": a street with no type
        return Parsed(int(t[0]), t[1], " ".join(rest), None, "")
    return Parsed(int(t[0]), t[1], " ".join(rest[:ti]), _TYPE_ALIAS.get(rest[ti], rest[ti]), " ".join(rest[ti + 1:]))


def to_ft(geom):
    """A lon/lat geometry in local feet (equirectangular at Chicago's latitude)."""
    return shapely.transform(geom, lambda xy: xy * np.array([_FT_PER_DEG_LON, _FT_PER_DEG_LAT]))


@dataclass
class _Face:
    line: Any  # LineString in feet, digitized from -> to
    left: tuple[int, int]
    right: tuple[int, int]
    left_parity: str | None
    right_parity: str | None


class Streets:
    """The street centerlines by (predir, name, type), in feet, for block-face checks."""

    def __init__(self, rows: Iterable[tuple]):
        faces: dict[tuple, list[_Face]] = {}
        for predir, name, typ, lf, lt, rf, rt, lp, rp, wkb in rows:
            g = to_ft(shapely.from_wkb(wkb))
            if g.geom_type == "MultiLineString":
                g = shapely.line_merge(g)
                if g.geom_type == "MultiLineString":
                    g = max(g.geoms, key=lambda x: x.length)
            if g.is_empty or g.length < 1:
                continue
            faces.setdefault((predir, name, typ or None), []).append(
                _Face(g, (int(lf or 0), int(lt or 0)), (int(rf or 0), int(rt or 0)), lp, rp))
        self._faces = faces
        self._trees = {k: STRtree([f.line for f in v]) for k, v in faces.items()}
        types: dict[tuple[str, str], set] = {}
        for predir, name, typ in faces:
            types.setdefault((predir, name), set()).add(typ)
        self._types = types

    def resolve(self, p: Parsed) -> Parsed | None:
        """``p`` spelled as the City's centerlines spell its street, or None when no street matches: "SAINT" is "ST",
        the King Drive variants are one name, and a street type the City does not use for that name is replaced
        when the name has exactly one (``N BROADWAY ST`` is ``N BROADWAY``)."""
        name = _NAME_ALIAS.get(p.name, p.name)
        if name.startswith("SAINT "):
            name = "ST " + name[6:]
        if (p.predir, name, p.typ) in self._faces:
            return Parsed(p.number, p.predir, name, p.typ, p.unit)
        typs = self._types.get((p.predir, name), set())
        if len(typs) == 1:
            return Parsed(p.number, p.predir, name, next(iter(typs)), p.unit)
        return None

    def check(self, p: Parsed, lot_ft) -> tuple[bool, str, float | None]:
        """Does ``p``'s number fall on this lot's block face? -> (ok, reason, the number the lot's position implies)."""
        tree = self._trees.get(p.street)
        if tree is None:
            return False, "no_street", None
        faces = self._faces[p.street]  # callers pass ``resolve``d addresses
        idx = tree.query(lot_ft, predicate="dwithin", distance=MAX_STREET_FT)
        if len(idx) == 0:
            return False, "street_far", None
        dists = sorted((faces[i].line.distance(lot_ft), i) for i in idx)
        best = None
        c = lot_ft.centroid
        for d, i in dists:
            if d > dists[0][0] + 1.0:  # only the nearest face (or faces tied with it at a block end)
                break
            f = faces[i]
            s = f.line.project(c)
            a = f.line.interpolate(max(s - 1.0, 0.0))
            b = f.line.interpolate(min(s + 1.0, f.line.length))
            left = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x) > 0
            lo_hi, parity = (f.left, f.left_parity) if left else (f.right, f.right_parity)
            lo, hi = sorted(lo_hi)
            expected = lo_hi[0] + (lo_hi[1] - lo_hi[0]) * s / f.line.length
            in_range = hi > 0 and lo <= p.number <= hi
            parity_ok = parity not in ("O", "E") or (parity == "O") == (p.number % 2 == 1)
            if not (in_range and parity_ok):
                best = best or (False, "off_block_face", expected)
                continue
            if abs(p.number - expected) > TOLERANCE_NUMBERS:
                best = (False, "off_position", expected)
                continue
            return True, "ok", expected
        return best


class AddressSources:
    """The address tables of the local copy (``lot_sources``), read for a batch of lots."""

    def __init__(self, path: Path):
        self.path = path
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            self.streets = Streets(db.execute(
                "SELECT pre_dir, name, typ, l_f, l_t, r_f, r_t, l_parity, r_parity, wkb FROM centerlines"))
        finally:
            db.close()

    @classmethod
    def load(cls, path: Path) -> "AddressSources | None":
        """None when the copy predates the address tables (a copy made before Item 109)."""
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                db.close()
        except sqlite3.Error:
            return None
        if not {"assessor_address", "address_points", "centerlines"} <= have:
            return None
        return cls(path)

    def lookup(self, pin14s: Iterable[str]) -> tuple[dict[str, str], dict[str, list[tuple[float, float]]]]:
        """pin14 -> the Assessor's address, and base address (the City's spelling) -> its Address Points (lon, lat)."""
        pins = sorted(set(pin14s))
        out: dict[str, str] = {}
        points: dict[str, list[tuple[float, float]]] = {}
        db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        try:
            for i in range(0, len(pins), 900):
                chunk = pins[i:i + 900]
                marks = ",".join("?" * len(chunk))
                out.update(db.execute(f"SELECT pin14, address FROM assessor_address WHERE pin14 IN ({marks})", chunk))
            bases = sorted({r.base for r in (self.streets.resolve(p) for p in map(parse, out.values()) if p) if r})
            for i in range(0, len(bases), 900):
                chunk = bases[i:i + 900]
                marks = ",".join("?" * len(chunk))
                for addr, lon, lat in db.execute(
                        f"SELECT address, lon, lat FROM address_points WHERE address IN ({marks})", chunk):
                    points.setdefault(addr, []).append((lon, lat))
        finally:
            db.close()
        return out, points


def verified_address(assessor: str | None, lot, streets: Streets,
                     points: dict[str, list[tuple[float, float]]] | None) -> tuple[str | None, str]:
    """The Assessor's address (without its unit tail, the street spelled as the City spells it) when it lands on
    ``lot`` (lon/lat), else None; with the reason. ``points`` = base address -> its Address Points."""
    raw = parse(assessor)
    if raw is None:
        return None, "no_address" if not assessor else "placeholder"
    p = streets.resolve(raw)
    if p is None:
        return None, "no_street"
    lot_ft = to_ft(lot)
    ok, reason, _expected = streets.check(p, lot_ft)
    if not ok:
        return None, reason
    at = (points or {}).get(p.base)
    if at:
        near = min(to_ft(shapely.Point(lon, lat)).distance(lot_ft) for lon, lat in at)
        if near > AP_ELSEWHERE_FT:
            return None, "address_point_elsewhere"
    return p.base, "ok"


def apply(attrs: dict[str, Any], address: str | None) -> None:
    """Set (or clear) the Assessor tier on one lot's attrs, in place; reruns are idempotent.

    ``address_nearest`` keeps the ``~`` nearest address the tier replaced, so a rerun whose check now fails restores it.
    ``own_address`` is left as it was (the City's Address Points only), so what Discovery hides by default is unchanged.
    """
    if attrs.pop("address_source", None) == "assessor":
        near = attrs.pop("address_nearest", None)
        if near:
            attrs["address"] = near
        else:
            attrs.pop("address", None)
    attrs.pop("address_nearest", None)
    if address is None:
        return
    current = attrs.get("address")
    if current and not str(current).startswith("~"):
        return  # an Address Point of its own (or its building's) always wins
    if current:
        attrs["address_nearest"] = current
    attrs["address"] = address
    attrs["address_source"] = "assessor"


def needs_tier(attrs: dict[str, Any]) -> bool:
    """A lot whose shown address is approximate (``~``), missing, or set by this tier on an earlier run."""
    a = attrs.get("address")
    return attrs.get("address_source") == "assessor" or not a or str(a).startswith("~")
