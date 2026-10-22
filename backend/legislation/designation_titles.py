"""Parse a Chicago Landmark designation ordinance title into the name and the street segments it lists.

Council designates a landmark by ordinance, and the City's landmark map layers take weeks to months to
show it. A title reads ``Historical landmark designation for Erie Street Row at 161 E Erie St`` (one
building), or names a district by blocks: ``... Bryn Mawr Avenue District located at 900 through 1100
blocks of W Bryn Mawr Ave``. The daily sync turns each listed address or block range into parcels
(Address Points) so the Profile can say "a landmark designation ordinance listing this address passed".

The rules are the rezoning parser's (``address_titles``), with this grammar added:

- **Never guess.** A title the parser cannot fully account for is ``partial`` and gets no parcel flag: a street
  with no recognizable type ("5830 W Midway Park"), a side of the street on the wrong axis, leftover text.
- **A block is a hundred.** "1600-1800 blocks" is house numbers 1600 through 1899; "900 block" is 900 through 999.
- **A side is a parity.** Chicago numbers even on the east side of a north-south street and the north side of
  an east-west street, odd on the other. "East Side of 900 block of N Sacramento Blvd" is the even numbers
  900-998.
- **A district names blocks, not parcels.** Its boundary is in the ordinance text, so a parcel on a listed
  block is "on a block the title names", never "inside the district" (``kind`` is ``district``).

Pure functions, no network. ``PARSER_VERSION`` goes into the snapshot so a parser change recomputes every row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.legislation.address_titles import (
    _DIRECTION, _SPLIT, WIDE_RANGE, Segment, _street, side_of,
)

PARSER_VERSION = 1

_PREFIX = re.compile(r"^Historical landmark designation for\s+(?P<name>.+?)\s+(?:located\s+)?at\s+(?=\d|(?:North|South|East|West)\s+side)(?P<rest>.+)$", re.I)
_ADDRESS = re.compile(r"^(?P<num>\d+)\s+(?P<dir>[NSEW])\s+(?P<street>.+)$", re.I)
_BLOCKS = re.compile(
    r"^(?:(?P<side>North|South|East|West)\s+side\s+of\s+)?(?P<lo>\d+)(?:\s*(?:-|through|to)\s*(?P<hi>\d+))?\s+blocks?\s+of\s+"
    r"(?P<dir>[NSEW])\s+(?P<street>.+)$", re.I,
)
_DISTRICT = re.compile(r"\bdistrict\b", re.I)


@dataclass
class ParsedDesignation:
    status: str                      # "clean" | "partial" | "unparsed"
    name: str | None = None
    kind: str = "building"           # "building" | "district"
    segments: list[Segment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status, "name": self.name, "kind": self.kind,
            "segments": [s.as_dict() for s in self.segments], "notes": self.notes, "parser": PARSER_VERSION,
        }


def _side_parity(street_dir: str, side_word: str, notes: list[str]) -> str | None:
    """"east side" of a north-south street → even; "north side" of an east-west street → even; the others odd.
    A side on the wrong axis ("east side" of W Bryn Mawr) is a title we do not understand, so None."""
    side = side_word.lower()
    if street_dir in ("N", "S"):
        if side in ("east", "west"):
            return "even" if side == "east" else "odd"
    elif side in ("north", "south"):
        return "even" if side == "north" else "odd"
    notes.append(f"{side} side of a {street_dir} street")
    return None


def parse_title(title: str) -> ParsedDesignation:
    text = re.sub(r"\s+", " ", title or "").strip()
    m = _PREFIX.match(text)
    if not m:
        return ParsedDesignation("unparsed", notes=["not a landmark designation title we read"])
    name = m.group("name").strip()
    out = ParsedDesignation("clean", name=name, kind="district" if _DISTRICT.search(name) else "building")
    rest = re.sub(r"\ba\.k\.a\.?", ";", m.group("rest"), flags=re.I)

    for item in (i.strip() for i in _SPLIT.split(rest)):
        if not item:
            continue
        bm = _BLOCKS.match(item)
        am = None if bm else _ADDRESS.match(item)
        if not (bm or am):
            out.notes.append(f"unparsed text {item!r}")
            continue
        g = (bm or am)
        direction = _DIRECTION[g.group("dir").upper()]
        street = _street(g.group("street"), out.notes)
        if street is None:
            continue
        sname, styp = street
        if bm:
            lo = int(bm.group("lo"))
            hi = int(bm.group("hi") or lo) + 99
            if int(bm.group("hi") or lo) < lo:
                out.notes.append(f"reversed blocks {item!r}")
                continue
            if hi - lo > WIDE_RANGE:
                out.notes.append(f"very wide range {item!r}")
                continue
            side = "both"
            if bm.group("side"):
                side = _side_parity(direction, bm.group("side"), out.notes) or "both"
                if side == "both":
                    continue  # the note says why: never widen a side we could not read
            out.kind = "district"
            out.segments.append(Segment(direction, sname, styp, lo, hi, side, raw=f"{lo}-{hi}"))
        else:
            num = int(am.group("num"))
            if num >= 1_000_000:
                out.notes.append(f"fused number {item!r}")
                continue
            out.segments.append(Segment(direction, sname, styp, num, num, side_of(num, num), raw=str(num)))

    if not out.segments:
        out.status = "unparsed"
    elif out.notes:
        out.status = "partial"
    return out
