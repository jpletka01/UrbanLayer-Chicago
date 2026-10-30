"""How current the law we serve is: the code text's vintage plus what City Council has
passed since. Pure and offline (WS1 M2; plan §5.1, §5.6, §7.3).

Three inputs, no network:

- ``backend/code_vintage.json``: the code text's "current through" date (ingestion).
- ``backend/code_amendments.json``: committed, hand-reviewed meaning of each amendment.
- the legislation snapshot (``settings.legislation_snapshot_path``), written daily by
  ``backend.legislation.sync`` from the Clerk API and re-read when its mtime changes.

The live list says WHAT passed; the review file says what it MEANS. An amendment the
sync found but nobody reviewed still shows, as unreviewed, with its title and link.

**Never claim "none passed" without a fresh check.** How much we may say depends on the
snapshot's age (:func:`check_state`): fresh (< 72 h) gives the count; aging (3-14 days)
gives it "as of" the check; unknown (> 14 days, never, or a suspect snapshot) gives no
count at all. Committed ``codified: false`` amendments are listed in every state, so a
Clerk outage never hides TOD Streets.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from backend.code_vintage import get_code_vintage, get_code_vintage_record
from backend.legislation.amendments import normalize_section, sections_overlap

log = logging.getLogger(__name__)

REVIEW_FILE = Path(__file__).resolve().parent.parent / "code_amendments.json"
# Tests point this at a temp file; None = settings.legislation_snapshot_path.
SNAPSHOT_FILE: Path | None = None

CHICAGO = ZoneInfo("America/Chicago")
CLERK_SITE_URL = "https://chicityclerkelms.chicago.gov/"
FRESH_HOURS = 72
AGING_DAYS = 14
DEFAULT_SCOPE = ("title17",)
ALL_SCOPES = ("title17", "cited_other")

# What the context, API and report carry for each amendment.
PUBLIC_FIELDS = (
    "record", "passed_on", "title", "summary", "summary_basis", "sections", "url", "relevance", "kind",
    "review_status", "product_effect", "codified",
)

_json_cache: dict[Path, tuple[int, object]] = {}


# --- loading ----------------------------------------------------------------------------------

def snapshot_path() -> Path:
    if SNAPSHOT_FILE is not None:
        return SNAPSHOT_FILE
    from backend.config import get_settings

    return get_settings().legislation_snapshot_path


def _read_json(path: Path):
    """The parsed file, re-read only when its mtime changes; None when missing/unreadable."""
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        _json_cache.pop(path, None)
        return None
    hit = _json_cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        log.warning("Unreadable legislation file: %s", path)
        data = None
    _json_cache[path] = (mtime, data)
    return data


def load_reviews() -> dict[str, dict]:
    data = _read_json(REVIEW_FILE)
    return dict((data or {}).get("amendments") or {}) if isinstance(data, dict) else {}


def load_snapshot() -> dict | None:
    data = _read_json(snapshot_path())
    return data if isinstance(data, dict) else None


# --- state ------------------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def check_state(snapshot: dict | None, now: datetime | None = None) -> str:
    """fresh (< 72 h) | aging (3-14 days) | unknown (> 14 days, never checked, or suspect)."""
    if not snapshot or snapshot.get("status") == "suspect":
        return "unknown"
    checked = _parse_dt(snapshot.get("checked_at"))
    if checked is None:
        return "unknown"
    age = _now(now) - checked
    if age < timedelta(hours=FRESH_HOURS):
        return "fresh"
    if age <= timedelta(days=AGING_DAYS):
        return "aging"
    return "unknown"


def vintage_day() -> date | None:
    v = get_code_vintage()
    try:
        return date.fromisoformat(v["current_through"]) if v else None
    except ValueError:
        return None


# --- the amendment list -----------------------------------------------------------------------

def _merged(snapshot: dict | None) -> dict[str, dict]:
    """Every amendment we know of: the snapshot's live rows (unless the snapshot is
    suspect) overlaid with the review file. A stale snapshot's rows are still true, so
    they stay listed; only the count depends on freshness."""
    reviews = load_reviews()
    out: dict[str, dict] = {}
    live = (snapshot or {}).get("code_amendments") if (snapshot or {}).get("status") != "suspect" else None
    for row in live or []:
        if not isinstance(row, dict) or not row.get("record") or row.get("relevance") not in ALL_SCOPES:
            continue
        out[row["record"]] = {
            **{k: row.get(k) for k in ("record", "url", "title", "passed_on", "relevance", "kind")},
            "sections": list(row.get("sections") or []),
            "summary": None, "summary_basis": None,
            "review_status": "unreviewed", "product_effect": "pending",
            "codified": False, "map_effects": [],
        }
    for rec, review in reviews.items():
        base = out.get(rec, {})
        out[rec] = {**base, **{k: v for k, v in review.items() if not k.startswith("_")}}
    return out


def _sorted(rows: Iterable[dict]) -> list[dict]:
    return sorted(rows, key=lambda a: (a.get("passed_on") or "", a.get("record") or ""), reverse=True)


def amendments_since(day: date, scope: tuple[str, ...] = DEFAULT_SCOPE) -> list[dict]:
    """THE "N amendments passed since <day>" function (WS1 disclosure and WS6's
    "since then"): amendments in ``scope`` passed after ``day``, newest first."""
    rows = _merged(load_snapshot()).values()
    return _sorted(a for a in rows if a.get("relevance") in scope and (a.get("passed_on") or "") > day.isoformat())


def amendments_since_vintage(scope: tuple[str, ...] = DEFAULT_SCOPE) -> list[dict]:
    """Passed after the code text's vintage, plus any reviewed as not yet in our text
    (``codified: false``) whatever its date."""
    day = vintage_day()
    rows = _merged(load_snapshot()).values()
    return _sorted(
        a for a in rows if a.get("relevance") in scope
        and ((day is not None and (a.get("passed_on") or "") > day.isoformat()) or a.get("codified") is False)
    )


def amendments_touching(section_id: str, scope: tuple[str, ...] = ALL_SCOPES) -> list[dict]:
    """Amendments not in our text that touch ``section_id``: its subsections, the section
    containing it, the chapter, or (for an indexed article id) any section in the article."""
    return [a for a in amendments_since_vintage(scope) if any(sections_overlap(section_id, s) for s in a.get("sections") or [])]


def public(a: dict, **extra) -> dict:
    return {**{k: a.get(k) for k in PUBLIC_FIELDS}, **extra}


# --- per parcel --------------------------------------------------------------------------------

# Sections a Profile states facts from, beyond the bulk table (provenance.BULK_SECTIONS):
# the family's use table, and the code behind each overlay it shows.
USE_TABLE_SECTIONS = {"R": "17-2-0207", "BC": "17-3-0207", "D": "17-4-0207", "M": "17-5-0207"}
# Not pedestrian_street: §17-3-0503-D is the LIST of designated streets, so an amendment
# adding Belmont doesn't touch a Halsted parcel; reviewed map_effects carry that instead.
OVERLAY_SECTIONS = {
    "adu_area": "17-7-0574",
    "tod_cta": "17-10-0102-B",
    "landmark_building": "2-120-740",
    "landmark_district": "2-120-740",
}
# Special districts by the name the City's layer gives them -> their article.
SPECIAL_DISTRICT_SECTIONS = {
    "milwaukee avenue special character overlay": "17-7-1500",
}


def parcel_cited_sections(zone_class: str | None, overlays: Iterable = (), note_sections: Iterable[str] = ()) -> list[str]:
    """Every section the Profile for this parcel cites: bulk standards, use table,
    overlays, coverage notes. An amendment touching one is parcel-relevant."""
    from backend.provenance import BULK_SECTIONS, bulk_family

    out: list[str] = []
    fam = bulk_family(zone_class)
    if fam:
        out += [s for s in BULK_SECTIONS[fam].values() if s]
        out.append(USE_TABLE_SECTIONS[fam])
    for o in overlays:
        t = getattr(o, "layer_type", None)
        if t in OVERLAY_SECTIONS:
            out.append(OVERLAY_SECTIONS[t])
        name = (getattr(o, "name", None) or "").lower()
        out += [sec for key, sec in SPECIAL_DISTRICT_SECTIONS.items() if t == "special_district" and key in name]
    out += [s for s in note_sections if s]
    return list(dict.fromkeys(out))

def address_parts(address: str | None) -> tuple[int, str, str] | None:
    if not address:
        return None
    from backend.retrieval.buildings import parse_chicago_address

    parts = parse_chicago_address(address.split(",")[0])
    if not parts:
        return None
    try:
        return int(parts["number"]), parts["direction"].upper(), re.sub(r"\s+", " ", parts["name"]).upper()
    except (KeyError, ValueError):
        return None


def address_suffix(address: str | None) -> str | None:
    """The street-type word of an address ("AVE" in "3036 W Lawrence Ave"), None when it has none."""
    if not address:
        return None
    from backend.retrieval.buildings import _SUFFIXES

    m = re.search(r"\s(" + _SUFFIXES[3:-1] + r")\b(?:\s.*|,.*)?$", address.split(",")[0].strip().upper())
    return m.group(1) if m else None


def suffix_conflicts(want: str | None, address: str | None) -> bool:
    """A named street type that the address contradicts ("Lawrence Pl" is not "Lawrence Ave")."""
    have = address_suffix(address)
    return bool(want and have and want.upper() != have)


def map_effect_matches(effect: dict, address: str | None, overlay_types: Iterable[str] = ()) -> bool:
    """Whether a reviewed map effect reaches this address. A street segment needs its
    number range; a pedestrian-street removal without a range matches a parcel on that
    street that still shows the overlay. An addition without a range matches nothing
    (we'd be guessing the segment)."""
    parts = address_parts(address)
    if parts is None:
        return False
    number, direction, name = parts
    if effect.get("street", "").upper() != name or (effect.get("direction") or direction).upper() != direction:
        return False
    if suffix_conflicts(effect.get("suffix"), address):
        return False
    lo, hi = effect.get("from"), effect.get("to")
    if lo is not None and hi is not None:
        return lo <= number <= hi
    return effect.get("kind") == "pedestrian_street_removed" and "pedestrian_street" in set(overlay_types)


def _touches(a: dict, cited: list[str]) -> list[str]:
    return [c for c in cited if any(sections_overlap(c, s) for s in a.get("sections") or [])]


def chicago_day(iso: str) -> date:
    """A date, or a timestamp's date in Chicago. Raises ValueError on garbage."""
    dt = _parse_dt(iso) if "T" in iso else None
    return dt.astimezone(CHICAGO).date() if dt else date.fromisoformat(iso[:10])


def fmt_day(iso: str | None) -> str:
    """"Oct 20, 2026"."""
    try:
        d = chicago_day(iso or "")
    except ValueError:
        return iso or ""
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def code_currency(
    *,
    cited_sections: Iterable[str] = (),
    chunk_sections: Iterable[str] = (),
    address: str | None = None,
    overlay_types: Iterable[str] = (),
    only_touching: bool = False,
    now: datetime | None = None,
) -> dict | None:
    """What the context, the Profile, the section viewers and the report carry (plan §5.2).

    ``cited_sections`` are the sections the parcel's Profile cites; an amendment touching
    one, or whose map effect reaches ``address``, is ``parcel_relevant``.
    ``chunk_sections`` are the code chunks a chat turn retrieved. ``touches`` lists the
    cited or retrieved sections an amendment overlaps. Title 17 amendments are always
    listed; other titles only when they touch something. ``only_touching`` (a
    parcel-less chat turn) keeps just the touching ones. None when the vintage file is
    missing."""
    vintage = get_code_vintage()
    if not vintage:
        return None
    snapshot = load_snapshot()
    state = check_state(snapshot, now)
    cited = list(dict.fromkeys(normalize_section(s) for s in cited_sections if s))
    chunks = [c for c in dict.fromkeys(normalize_section(s) for s in chunk_sections if s) if c not in cited]
    overlay_types = list(overlay_types)

    rows: list[dict] = []
    for a in amendments_since_vintage(ALL_SCOPES):
        on_page = _touches(a, cited)
        touches = on_page + _touches(a, chunks)
        if a.get("relevance") != "title17" and not touches:
            continue
        if only_touching and not touches:
            continue
        on_map = any(map_effect_matches(e, address, overlay_types) for e in a.get("map_effects") or [])
        rows.append(public(a, parcel_relevant=bool(on_page) or on_map, touches=touches))
    rows.sort(key=lambda r: not r["parcel_relevant"])  # stable: relevant first, then newest first

    since = None
    if state != "unknown":
        all_since = amendments_since_vintage(ALL_SCOPES)
        since = {s: sum(1 for a in all_since if a.get("relevance") == s) for s in ALL_SCOPES}
    return {
        "current_through": vintage.get("current_through"),
        "label": vintage.get("label"),
        "source": vintage.get("source"),
        "checked_at": (snapshot or {}).get("checked_at") if state != "unknown" else None,
        "check_state": state,
        "since": since,
        "clerk_url": CLERK_SITE_URL,
        "amendments": rows,
    }


_MODEL_FIELDS = ("record", "passed_on", "title", "summary", "summary_basis", "sections", "codified", "parcel_relevant", "touches")


def for_model(cc: dict) -> dict:
    """``code_currency`` as the chat model gets it: full rows only for amendments that
    touch this parcel or the code in the context, record/date/title for the rest. The
    16 full rows were ~3k tokens on every parcel turn; links live in the Sources footer."""
    rows = []
    for a in cc.get("amendments") or []:
        if a.get("parcel_relevant") or a.get("touches"):
            rows.append({k: a.get(k) for k in _MODEL_FIELDS})
        else:
            rows.append({k: a.get(k) for k in ("record", "passed_on", "title")})
    return {k: v for k, v in cc.items() if k not in ("amendments", "source", "clerk_url")} | {"amendments": rows}


def currency_sentence(cc: dict) -> str:
    """One English sentence: the vintage, then what passed since, never "none" unless
    the check is fresh. The Profile note, the chat footer and the report share it."""
    label = cc.get("label") or f"through {cc.get('current_through')}"
    head = f"Municipal Code text: current through the {label}." if cc.get("label") else f"Municipal Code text: current {label}."
    since = cc.get("since")
    if since is None:
        return f"{head} We couldn't check for later amendments recently; the City Clerk's site lists them."
    n = since.get("title17", 0)
    checked = fmt_day(cc.get("checked_at"))
    things = f"{n} amendment{'s' if n != 1 else ''} to the Zoning Ordinance (Title 17)"
    not_in = f"that {'are' if n != 1 else 'is'} not in this text"
    if cc.get("check_state") == "aging":
        if n == 0:
            return f"{head} As of {checked}, City Council had passed no amendments to the Zoning Ordinance (Title 17) since then."
        return f"{head} As of {checked}, City Council had passed {things} since then {not_in}."
    if n == 0:
        return f"{head} City Council has passed no amendments to the Zoning Ordinance (Title 17) since then (checked {checked})."
    return f"{head} Since then City Council has passed {things} {not_in} (checked {checked})."


# --- the WS6 interface (plan §7.3): no network, admin-only endpoint ----------------------------

WARN_DAYS, ALARM_DAYS = 60, 90


def code_currency_status(now: datetime | None = None) -> dict:
    """Status of the code text for WS6's registry (``code.municipal_text``). The
    thresholds and status here are WS1's suggestion; WS6's registry decides."""
    now = _now(now)
    record = get_code_vintage_record() or {}
    day = vintage_day()
    snapshot = load_snapshot()
    state = check_state(snapshot, now)
    since = amendments_since_vintage(ALL_SCOPES)
    title17 = [a for a in since if a.get("relevance") == "title17"]
    unreviewed = [a for a in title17 if a.get("review_status") != "reviewed"]
    oldest = min((date.fromisoformat(a["passed_on"]) for a in unreviewed if a.get("passed_on")), default=None)
    age = (now.date() - day).days if day else None

    reasons: list[str] = []
    status = "green"
    if age is None:
        status, reasons = "red", ["no code vintage"]
    elif age > ALARM_DAYS:
        status = "red"
        reasons.append(f"code text {age} days old (> {ALARM_DAYS})")
    elif age > WARN_DAYS:
        status = "amber"
        reasons.append(f"code text {age} days old (> {WARN_DAYS})")
    if state == "unknown":
        status = "red" if status == "red" else "amber"
        reasons.append("no fresh check of the Clerk's list of passed amendments")
    return {
        "source_id": "code.municipal_text",
        "as_of": record.get("current_through"),
        "as_of_kind": "council_journal",
        "ingested_at": (record.get("ingested_at") or "")[:10] or None,
        "age_days": age,
        "lag": {
            "title17_passed_since": len(title17) if state != "unknown" else None,
            "cited_other_passed_since": sum(1 for a in since if a.get("relevance") == "cited_other") if state != "unknown" else None,
            "unreviewed": len(unreviewed),
            "oldest_unreviewed_days": (now.date() - oldest).days if oldest else None,
            "uncodified_applied": sum(1 for a in since if a.get("codified") is False and a.get("product_effect") == "applied"),
        },
        "last_checked": (snapshot or {}).get("checked_at"),
        "check_state": state,
        "status": status,
        "reasons": reasons,
    }


def review_backlog(today: date) -> dict[str, list[dict]]:
    """Passed amendments nobody has reviewed yet, by how long each has waited since Council passed it
    (oldest first), for the registry's ``internal.amendment_review``. ``title17`` are the ones the
    Profile's rules rest on; ``cited_other`` touch sections the product cites. Offline."""
    out: dict[str, list[dict]] = {scope: [] for scope in ALL_SCOPES}
    for a in amendments_since_vintage(ALL_SCOPES):
        if a.get("review_status") == "reviewed" or not a.get("passed_on") or a.get("relevance") not in out:
            continue
        out[a["relevance"]].append({
            "record": a["record"], "passed_on": a["passed_on"],
            "waiting_days": (today - date.fromisoformat(a["passed_on"])).days,
        })
    for rows in out.values():
        rows.sort(key=lambda r: (r["passed_on"], r["record"]))
    return out


def clerk_source_status() -> dict:
    """Status of the Clerk feed for WS6's registry (``chi.clerk.legislation``)."""
    s = load_snapshot() or {}
    return {
        "source_id": "chi.clerk.legislation",
        "last_success": s.get("checked_at"),
        "last_attempt": s.get("last_attempt_at"),
        "last_error": s.get("last_error"),
        "consecutive_failures": s.get("consecutive_failures", 0),
        "snapshot_state": s.get("status") or "missing",
        "contract_ok": s.get("status") not in ("suspect",) and not s.get("contract_problems"),
        "contract_problems": s.get("contract_problems") or [],
    }


def map_lag_status() -> dict:
    """Status of "passed but not yet on the City map" for WS6's registry (``chi.zoning.passed_not_on_map``)
    and the admin card: how many passed rezonings the zoning map lacks, how long the oldest has waited, and
    the titles we could not place. Counts are null when the rezoning check has never succeeded."""
    from backend.legislation import rezonings

    s = load_snapshot() or {}
    check = s.get("rezoning_check") or {}
    rows = s.get("rezonings") or []
    ok = bool(check.get("checked_at"))
    n = rezonings.summary(rows) if ok else {}
    return {
        "source_id": "chi.zoning.passed_not_on_map",
        "passed_not_on_map": n.get("off_map"),
        "oldest_days": n.get("off_map_oldest_days"),
        "flaggable": n.get("flaggable"),
        "with_parcels": n.get("with_parcels"),
        "unparsed_titles": len(n["unparsed"]) if ok else None,
        "unparsed": n.get("unparsed") or [],
        "no_parcels": n.get("no_parcels") or [],
        "district_read_agreement": None,  # WS1 M6
        "check_status": check.get("status") or "missing",
        "last_checked": check.get("checked_at"),
        "last_error": check.get("last_error"),
    }


def designation_status() -> dict:
    """Status of "a landmark designation passed that the map doesn't show on the parcel yet" for the admin card:
    how many recent designations we could place on a parcel, and the titles we could not. Counts are null when
    the designation check has never succeeded."""
    from backend.legislation import designations

    s = load_snapshot() or {}
    check = s.get("designation_check") or {}
    ok = bool(check.get("checked_at"))
    n = designations.summary(s.get("designations") or []) if ok else {}
    return {
        "passed": n.get("passed"),
        "flaggable": n.get("flaggable"),
        "with_parcels": n.get("with_parcels"),
        "unparsed_titles": len(n["unparsed"]) if ok else None,
        "unparsed": n.get("unparsed") or [],
        "no_parcels": n.get("no_parcels") or [],
        "check_status": check.get("status") or "missing",
        "last_checked": check.get("checked_at"),
        "last_error": check.get("last_error"),
    }

