"""Parse a zoning-reclassification ordinance title into the street segments it names.

A title reads ``Zoning Reclassification Map No. 7-H at 2328-2334 W Montana St. - App No.
23167T1``; the legal description is the list of address ranges after "at". The daily sync
turns each range into the parcels it covers (Address Points) so the Profile can say "a
rezoning listing this address passed, and the City's map hasn't caught up".

Rules (WS1 plan §6.1):

- **Never guess.** A title the parser cannot fully account for is ``partial``: it gets no
  parcel flag and is listed for manual mapping (``backend/rezoning_overrides.json``). That
  covers fused numbers ("34013551"), a street name that is not a plain word or ordinal
  ("75t"), a missing street type, a reversed range, and any text left over.
- **Parity.** Both ends odd → the odd side only; both even → the even side only; mixed
  parity or a single number → both sides (a single number names a lot, and Address Points
  may number it on either parity).
- **Lists share a street.** "1300-1422 and 1301-1511 W Cortland St" is two ranges on one
  street; "a.k.a." adds the second address of the same land.

Pure functions, no network. ``PARSER_VERSION`` goes into the snapshot so a parser change
recomputes every stored row.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

PARSER_VERSION = 1

# Street types as the City writes them in titles → the full word Address Points stores
# (``st_postyp``). Both forms are matched in the query.
STREET_TYPES: dict[str, str] = {
    "ST": "STREET", "AVE": "AVENUE", "BLVD": "BOULEVARD", "DR": "DRIVE", "PL": "PLACE", "RD": "ROAD",
    "CT": "COURT", "PKWY": "PARKWAY", "TER": "TERRACE", "LN": "LANE", "CIR": "CIRCLE", "HWY": "HIGHWAY",
    "SQ": "SQUARE", "PLZ": "PLAZA", "WAY": "WAY", "ALY": "ALLEY", "ROW": "ROW", "TRL": "TRAIL",
}

_TYPE_BY_WORD = {word: abbr for abbr, word in STREET_TYPES.items()}

# Spelled-out ordinals Chicago uses for street names ("W Fifth Ave"); Address Points may hold
# either form, so the resolver tries both.
_ORDINAL_WORDS = {
    "FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH", "FIFTH": "5TH", "SIXTH": "6TH",
    "SEVENTH": "7TH", "EIGHTH": "8TH", "NINTH": "9TH", "TENTH": "10TH", "ELEVENTH": "11TH", "TWELFTH": "12TH",
}
_ORDINAL_NUM = re.compile(r"^\d+(ST|ND|RD|TH)$")
_WORD = re.compile(r"^[A-Z][A-Z'\-]*$")
_DIRECTION = {"N": "N", "S": "S", "E": "E", "W": "W"}

_PREFIX = re.compile(
    r"^Zoning Reclassification Map Nos?\.?\s*(?P<maps>.+?)(?:\s+at\s+|-at\s+)(?P<rest>.+)$", re.I,
)
# "… St - App No. 23167T1", "… St- App No. 23009T1", "… Ave App No. A-8925" (no dash), "… - A-9059" (no label)
_APP_NO = re.compile(
    r"(?:\s*-\s*|\s+)App\.?\s*No\.?\s*(?P<app>[A-Z]-\d+|\d+T?\d*)\s*$|\s+-\s+(?P<bare>[A-Z]-\d+|\d+T?\d*)\s*$", re.I,
)
_ITEM = re.compile(r"^(?P<nums>\d+(?:\s*-\s*\d+)?)(?:\s+(?P<dir>[NSEW])\s+(?P<street>.+))?$", re.I)
_SPLIT = re.compile(r"\s*(?:;|/|,(?!\s*Jr\b)|\band\b)\s*", re.I)
# A range wider than this is read, but noted: a typo in a title would otherwise claim a neighborhood.
WIDE_RANGE = 2500


@dataclass
class Segment:
    dir: str
    name: str            # as written, upper-cased, punctuation removed ("5TH", "FIFTH", "95TH")
    type: str | None     # the title's abbreviation ("ST"), upper-cased
    lo: int
    hi: int
    side: str            # "odd" | "even" | "both"
    raw: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedTitle:
    status: str                              # "clean" | "partial" | "unparsed"
    segments: list[Segment] = field(default_factory=list)
    maps: str | None = None
    app_no: str | None = None
    notes: list[str] = field(default_factory=list)   # why a title is partial, for the admin list

    def as_dict(self) -> dict:
        return {
            "status": self.status, "segments": [s.as_dict() for s in self.segments],
            "maps": self.maps, "app_no": self.app_no, "notes": self.notes, "parser": PARSER_VERSION,
        }


def side_of(lo: int, hi: int) -> str:
    """Parity rule: both ends odd → odd; both even → even; anything else → both."""
    if lo == hi:
        return "both"
    if lo % 2 == hi % 2:
        return "odd" if lo % 2 else "even"
    return "both"


def name_candidates(name: str) -> list[str]:
    """The spellings to try against Address Points for one title street name, most likely first."""
    out = [name]
    parts = name.split()
    if name in _ORDINAL_WORDS:
        out.append(_ORDINAL_WORDS[name])
    for word, digits in _ORDINAL_WORDS.items():
        if digits == name:
            out.append(word)
    if parts and parts[0] == "DR" and len(parts) > 1:  # "Dr. Martin Luther King, Jr." → DOCTOR …
        out.append(" ".join(["DOCTOR", *parts[1:]]))
    if parts and parts[0] == "ST" and len(parts) > 1:  # "St. Lawrence" → SAINT …
        out.append(" ".join(["SAINT", *parts[1:]]))
    return list(dict.fromkeys(out))


def _clean_name(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[.,]", " ", raw)).strip().upper()


def _street(raw: str, notes: list[str]) -> tuple[str, str | None] | None:
    """``(name, type)`` from "Montana St." / "Dr. Martin Luther King, Jr. Dr" / "95th St", or None."""
    tokens = _clean_name(raw).split()
    if len(tokens) < 2:
        notes.append(f"street has no type: {raw!r}")
        return None
    typ = tokens[-1] if tokens[-1] in STREET_TYPES else _TYPE_BY_WORD.get(tokens[-1])  # "95th Street"
    if typ is None:
        notes.append(f"unknown street type in {raw!r}")
        return None
    name_tokens = tokens[:-1]
    for t in name_tokens:
        if not (_WORD.match(t) or _ORDINAL_NUM.match(t)):
            notes.append(f"suspect street name {raw!r}")  # "75t", "1st2": flagged, never repaired
            return None
    return " ".join(name_tokens), typ


def _range(nums: str, notes: list[str]) -> tuple[int, int] | None:
    parts = [p.strip() for p in nums.split("-")]
    if any(len(p) >= 7 for p in parts):
        notes.append(f"fused number {nums!r}")
        return None
    lo, hi = int(parts[0]), int(parts[-1])
    if lo > hi:
        notes.append(f"reversed range {nums!r}")
        return None
    if hi - lo > WIDE_RANGE:
        notes.append(f"very wide range {nums!r}")
        return None
    return lo, hi


def parse_title(title: str) -> ParsedTitle:
    text = re.sub(r"\s+", " ", title or "").strip()
    m = _PREFIX.match(text)
    if not m:
        return ParsedTitle("unparsed", notes=["not a Zoning Reclassification Map title"])
    out = ParsedTitle("clean", maps=m.group("maps").strip())
    rest = m.group("rest").strip()
    app = _APP_NO.search(rest)
    if app:
        out.app_no = (app.group("app") or app.group("bare")).upper()
        rest = rest[: app.start()]
    rest = re.sub(r"\ba\.k\.a\.?", ";", rest, flags=re.I)

    pending: list[tuple[int, int, str]] = []   # ranges waiting for the street that follows them
    for item in (i.strip() for i in _SPLIT.split(rest)):
        if not item:
            continue
        im = _ITEM.match(item)
        if not im:
            out.notes.append(f"unparsed text {item!r}")
            continue
        rng = _range(im.group("nums"), out.notes)
        if im.group("street") is None:
            if rng:
                pending.append((*rng, im.group("nums")))
            continue
        street = _street(im.group("street"), out.notes)
        direction = _DIRECTION[im.group("dir").upper()]
        todo = [*pending, (*rng, im.group("nums"))] if rng else list(pending)
        pending = []
        if street is None:
            continue
        name, typ = street
        for lo, hi, raw in todo:
            out.segments.append(Segment(direction, name, typ, lo, hi, side_of(lo, hi), raw=raw))
    if pending:
        out.notes.append("numbers with no street: " + ", ".join(p[2] for p in pending))
    if not out.segments:
        out.status = "unparsed"
    elif out.notes:
        out.status = "partial"
    return out
