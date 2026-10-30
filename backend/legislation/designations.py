"""Chicago Landmark designations Council has passed that the City's landmark map doesn't show on a parcel yet (WS1 M5b).

A designation ordinance reaches the Zoning MapServer's landmark layers (5, individual Chicago Landmarks; 6,
landmark and historic districts) weeks or months after it passes. In between, a Profile's overlays can read
"no landmark" for a parcel whose address the ordinance lists, and a landmark means the Commission on Chicago
Landmarks must approve permits to alter, demolish or build (§2-120-740).

**Why this is not the rezoning check.** A rezoning ordinance's record number is carried on the map polygon, so
"is it on the map yet?" has an exact answer. The landmark layers carry a name, an address and a designation
date as text, no ordinance number, so asking the same question of them would be a fuzzy name match. We don't.

**The rule instead, per parcel:** a recent designation ordinance's title lists this address, AND the parcel's
own landmark-layer result (the same overlay query the Profile already ran) does not already say landmark. If the
map shows the parcel as a landmark or in a landmark district there is nothing to add; if it doesn't, the
ordinance is news the map hasn't caught up to. No name is compared to anything.

**Daily, in the sync** (``build_rows``): the Clerk's passed ``HISTORICAL LANDMARKS | Designation`` matters of the
last ``LOOKBACK_DAYS``; each title is parsed (``designation_titles``) and its listed addresses and blocks are
resolved to parcels (Address Points, via the rezoning resolver). **Per parcel, no network** (``matches_for``).

What this says, and does not: "a designation ordinance *listing this address* passed on <date>". It never says
the parcel *is* a landmark. For a district the title names blocks, and the district's boundary is in the
ordinance text, so the words are "on a block the title names".
"""

from __future__ import annotations

from datetime import date

from backend.legislation import currency, rezonings
from backend.legislation.designation_titles import PARSER_VERSION, parse_title
from backend.retrieval import clerk

CATEGORY = "HISTORICAL LANDMARKS | Designation"
# How long after passing a designation is still flagged. The City says map amendments can take up to 90 days;
# eval/designation_backtest.py measures how long the landmark layers actually take (see the decision log).
LOOKBACK_DAYS = 180


def _base_row(m: clerk.ClerkMatter) -> dict:
    return {"record": m.record_number, "matter_id": m.matter_id, "url": m.url, "passed_on": m.passed_on.isoformat(),
            "title": m.title}


async def build_rows(matters: list[clerk.ClerkMatter], previous: list[dict] | None = None, *, client=None) -> list[dict]:
    """The snapshot's ``designations`` rows for these passed matters. Parsing and parcel resolution are reused
    from ``previous`` unless the parser version changed or the record is new; a failed resolution raises (the
    sync records the failed check and keeps the previous rows rather than store "no parcels")."""
    prev = {r["record"]: r for r in previous or [] if r.get("parser") == PARSER_VERSION and r.get("pins") is not None}
    rows: list[dict] = []
    for m in sorted(matters, key=lambda m: (m.passed_on, m.record_number)):
        row = _base_row(m)
        old = prev.get(m.record_number)
        if old:
            row.update({k: old.get(k) for k in ("parse", "parser", "pins", "unresolved")})
        else:
            row["parse"] = parse_title(m.title).as_dict()
            row["parser"] = PARSER_VERSION
            row["pins"], row["unresolved"] = None, []
        if row["pins"] is None:
            if row["parse"]["status"] == "clean":
                row["pins"], row["unresolved"] = await rezonings.resolve_pins(row["parse"]["segments"], client=client)
            else:
                row["pins"] = []
        rows.append(row)
    return rows


def summary(rows: list[dict], today: date | None = None) -> dict:
    """Counts for the sync log and the admin card."""
    today = today or date.today()
    recent = [r for r in rows if is_flaggable(r, today)]
    return {
        "passed": len(rows),
        "flaggable": len(recent),
        "with_parcels": sum(1 for r in recent if r.get("pins")),
        "unparsed": [r["record"] for r in rows if r["parse"]["status"] != "clean"],
        "no_parcels": [r["record"] for r in recent if r["parse"]["status"] == "clean" and not r.get("pins")],
    }


# --- per parcel (request path) -------------------------------------------------------------------

def is_flaggable(row: dict, today: date | None = None) -> bool:
    """A designation we can place: a clean parse, passed within the lookback."""
    if (row.get("parse") or {}).get("status") != "clean":
        return False
    try:
        age = ((today or date.today()) - date.fromisoformat(row["passed_on"])).days
    except (KeyError, ValueError):
        return False
    return 0 <= age <= LOOKBACK_DAYS


def map_shows_landmark(regulatory) -> bool:
    """The parcel's own overlay result already says landmark (a Chicago Landmark, or a landmark district)."""
    return bool(regulatory is not None and (regulatory.is_landmark_building or regulatory.in_landmark_district))


def landmark_layers_checked(regulatory) -> bool:
    """False when the landmark layers failed for this parcel: the map's answer is then unknown, and the words
    must not claim the map doesn't show it."""
    unchecked = set(getattr(regulatory, "unchecked_overlays", None) or [])
    return not (unchecked & {"landmark_building", "historic_district"})


def matches_for(
    pin: str | None, address: str | None, regulatory=None, snapshot: dict | None = None, today: date | None = None,
) -> list[dict]:
    """The recent designations that list this parcel, newest first. Empty when the map already shows the parcel
    as a landmark, or when the snapshot is unusable (failed/suspect, or not checked within 14 days: a stale
    list could name an ordinance the map has since caught up to)."""
    if map_shows_landmark(regulatory):
        return []
    snapshot = snapshot if snapshot is not None else currency.load_snapshot()
    if not snapshot or currency.check_state(snapshot) == "unknown" or snapshot.get("status") == "failed":
        return []
    parts = currency.address_parts(address)
    checked = landmark_layers_checked(regulatory)
    out: list[dict] = []
    for row in snapshot.get("designations") or []:
        if not is_flaggable(row, today):
            continue
        seg = None
        if pin and any(p[0] == pin for p in row.get("pins") or []):
            by = "pin"
            seg = _segment_for(row, address)
        elif not pin and parts:
            number, direction, name = parts
            seg = next((s for s in row["parse"]["segments"] if rezonings._segment_matches(s, number, direction, name, address)), None)
            by = "address"
        else:
            continue
        if by == "address" and seg is None:
            continue
        out.append({
            "record": row["record"], "passed_on": row["passed_on"], "url": row["url"],
            "name": row["parse"].get("name"), "kind": row["parse"].get("kind", "building"),
            "segment": _segment_text(seg or (row["parse"]["segments"] or [None])[0]),
            "map_checked": checked, "matched_by": by,
        })
    return sorted(out, key=lambda r: r["passed_on"], reverse=True)


def _segment_for(row: dict, address: str | None) -> dict | None:
    parts = currency.address_parts(address)
    if not parts:
        return None
    number, direction, name = parts
    return next((s for s in row["parse"]["segments"] if rezonings._segment_matches(s, number, direction, name, address)), None)


def _segment_text(seg: dict | None) -> str | None:
    """The listing's own words for the range: "161 E Erie St", "900-1199 W Bryn Mawr Ave"."""
    if not seg:
        return None
    rng = str(seg["lo"]) if seg["lo"] == seg["hi"] else f"{seg['lo']}-{seg['hi']}"
    return f"{rng} {seg['dir']} {seg['name'].title()} {(seg.get('type') or '').title()}".strip()

