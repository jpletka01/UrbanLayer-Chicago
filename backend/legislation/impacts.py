"""Which pending Title 17 text amendments a Profile may name (WS2 PR3).

Pure and offline. Three inputs:

- the pending snapshot's Title 17 text matters (``pending_store``, read-only; the daily sync is
  the only Clerk caller),
- ``backend/pending_impacts.json``: the committed, hand-reviewed meaning of each pending matter,
- the parcel's own current facts (zone class, overlays, the fact ids its Profile shows, address).

A pending proposal is named only when a committed review of the *current* record maps it to a
section or fact the Profile uses AND the parcel deterministically satisfies that mapping. A title
keyword never makes a proposal relevant, a title-only review can only say "no Profile fact", and
a matter with no current review keeps the Profile's review state ``incomplete`` instead of
quietly reading as "none". Nothing here touches a current-law number.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from backend.legislation import currency
from backend.legislation.amendments import normalize_section
from backend.models import (
    PendingTextAffectedFact,
    PendingTextEffect,
    PendingTextImpact,
    PendingTextReview,
    PendingTextUnreviewed,
    UpcomingZoningProvenance,
)

log = logging.getLogger(__name__)

REVIEW_FILE = Path(__file__).resolve().parent.parent / "pending_impacts.json"
CODE_AMENDMENTS = "MUNICIPAL CODE AMENDMENTS"
# Same clock as the passed-amendment review (internal.amendment_review): a Title 17 matter waits
# this long after Council introduced it before the backlog warns, then alarms.
REVIEW_WARN_DAYS = 14
REVIEW_ALARM_DAYS = 45

REACH = ("parcel", "untested")
CONDITION_KEYS = {"zone_patterns", "overlays_any", "overlays_none", "facts_all", "address_ranges"}
# Coverage notes are not fact ids, so a mapping names them ``note.*`` and must match by address.
NOTE_FACTS = {
    "note.tod_street": (
        "TOD street status",
        "Current law (17-3-0602-F) lists the TOD streets in force today; the proposal would add a segment.",
    ),
    "note.pedestrian_street": (
        "Pedestrian street status",
        "Current law (17-3-0503-D) lists the pedestrian streets in force today; the proposal would add a segment.",
    ),
}
_SECTION = re.compile(r"^\d{1,2}[A-Z]?-\d+(?:-[\dA-Z]+(?:\.\d+)*(?:-[A-Z])?)?$")


# --- the review file -----------------------------------------------------------------------------

def known_fact_ids() -> set[str]:
    from backend.provenance import FACTS

    return set(FACTS) | set(NOTE_FACTS)


def validate_review(lifecycle_id: str, review: object) -> list[str]:
    """Why a review entry cannot be trusted, or [] when it can. Used by the loader and the tests."""
    if not isinstance(review, dict):
        return [f"{lifecycle_id}: not an object"]
    problems: list[str] = []
    for key in ("reviewed_record", "title", "url", "reviewed_on", "reviewed_by", "basis"):
        if not review.get(key):
            problems.append(f"{lifecycle_id}: missing {key}")
    if review.get("review_status") != "reviewed":
        problems.append(f"{lifecycle_id}: review_status is not 'reviewed'")
    if review.get("basis") not in ("ordinance", "title"):
        problems.append(f"{lifecycle_id}: basis must be 'ordinance' or 'title'")
    impacts = review.get("impacts")
    if not isinstance(impacts, list):
        return problems + [f"{lifecycle_id}: impacts must be a list"]
    if impacts and review.get("basis") != "ordinance":
        problems.append(f"{lifecycle_id}: only an ordinance-basis review may carry impacts")
    if not impacts and not review.get("no_impact_reason"):
        problems.append(f"{lifecycle_id}: a review with no impacts needs a no_impact_reason")
    if impacts and not review.get("summary"):
        problems.append(f"{lifecycle_id}: impacts need a summary read from the text")
    known = known_fact_ids()
    seen: set[str] = set()
    for imp in impacts:
        iid = imp.get("id") if isinstance(imp, dict) else None
        tag = f"{lifecycle_id}/{iid}"
        if not iid or iid in seen:
            problems.append(f"{tag}: id missing or duplicated")
            continue
        seen.add(iid)
        if not imp.get("could_change"):
            problems.append(f"{tag}: could_change is required")
        sections = imp.get("sections") or []
        if not sections or any(not _SECTION.match(normalize_section(s)) for s in sections):
            problems.append(f"{tag}: sections must be Title 17 section ids")
        elif any(not normalize_section(s).startswith("17-") for s in sections):
            problems.append(f"{tag}: sections must be in Title 17")
        facts = imp.get("fact_ids") or []
        if not facts or any(f not in known for f in facts):
            problems.append(f"{tag}: fact_ids must name known Profile facts")
        when = imp.get("applies_when") or {}
        if set(when) - CONDITION_KEYS:
            problems.append(f"{tag}: unknown condition {sorted(set(when) - CONDITION_KEYS)}")
        for pattern in when.get("zone_patterns") or []:
            try:
                re.compile(pattern)
            except re.error:
                problems.append(f"{tag}: bad zone pattern {pattern!r}")
        if any(f not in known for f in when.get("facts_all") or []):
            problems.append(f"{tag}: facts_all names an unknown fact")
        if any(f.startswith("note.") for f in facts) and not when.get("address_ranges"):
            problems.append(f"{tag}: a coverage-note fact needs address_ranges")
        if not any(when.get(k) for k in CONDITION_KEYS - {"overlays_none"}):
            problems.append(f"{tag}: applies_when must say what makes a parcel match")
        if imp.get("reach") not in REACH:
            problems.append(f"{tag}: reach must be one of {REACH}")
        elif imp["reach"] == "untested" and not imp.get("reach_note"):
            problems.append(f"{tag}: an untested reach needs a reach_note")
    return problems


def load_reviews() -> dict[str, dict]:
    """Valid reviews by lifecycle id. An invalid entry is dropped (so its matter reads as
    unreviewed) and logged; it can never make a proposal relevant."""
    data = currency._read_json(REVIEW_FILE)
    raw = (data or {}).get("reviews") if isinstance(data, dict) else None
    out: dict[str, dict] = {}
    for lifecycle_id, review in (raw or {}).items():
        problems = validate_review(lifecycle_id, review)
        if problems:
            log.warning("Ignoring invalid pending impact review: %s", "; ".join(problems))
            continue
        out[lifecycle_id] = review
    return out


# --- the pending snapshot ----------------------------------------------------------------------

@dataclass(frozen=True)
class PendingText:
    matter_id: str
    lifecycle_id: str
    record_number: str
    title: str
    status: str
    sub_status: str
    introduced_at: str | None
    latest_action_at: str | None
    url: str


def read_text_matters(path: Path | str) -> list[PendingText]:
    """Every pending Title 17 text matter in the last-good snapshot (read-only; no network)."""
    p = Path(path)
    with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=2)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT m.*, (SELECT MAX(action_at) FROM actions a WHERE a.matter_id = m.matter_id) AS latest_action_at
               FROM matters m
               WHERE m.touches_title17 = 1 AND m.category LIKE ?
               ORDER BY COALESCE(m.introduced_at, m.created_at) DESC, m.record_number DESC""",
            (CODE_AMENDMENTS + "%",),
        ).fetchall()
    return [
        PendingText(
            matter_id=r["matter_id"], lifecycle_id=r["lifecycle_id"], record_number=r["record_number"],
            title=re.sub(r"\s+", " ", r["title"]).strip(), status=r["status"], sub_status=r["sub_status"],
            introduced_at=r["introduced_at"], latest_action_at=r["latest_action_at"], url=r["source_url"],
        )
        for r in rows
    ]


def review_state(matter: PendingText, reviews: dict[str, dict]) -> str:
    """``reviewed`` only when the review is of this exact current record. A newer substitute
    carries different text, so a review of the older record is ``outdated``."""
    review = reviews.get(matter.lifecycle_id)
    if review is None:
        return "unreviewed"
    return "reviewed" if review["reviewed_record"] == matter.record_number else "outdated"


def waiting_days(matter: PendingText, today: date) -> int | None:
    if not matter.introduced_at:
        return None
    try:
        return max(0, (today - datetime.fromisoformat(matter.introduced_at).astimezone(currency.CHICAGO).date()).days)
    except ValueError:
        return None


def backlog(matters: list[PendingText], reviews: dict[str, dict], today: date) -> list[dict]:
    """Matters with no current review, oldest first, for Data Health and the Profile."""
    rows = []
    for m in matters:
        state = review_state(m, reviews)
        if state != "reviewed":
            rows.append({"record": m.record_number, "reason": state, "waiting_days": waiting_days(m, today)})
    rows.sort(key=lambda r: (-(r["waiting_days"] if r["waiting_days"] is not None else -1), r["record"]))
    return rows


# --- one parcel --------------------------------------------------------------------------------

@dataclass(frozen=True)
class ParcelFacts:
    zone_class: str | None
    overlay_types: tuple[str, ...]
    address: str | None
    fact_ids: frozenset[str]
    # fact id -> the Profile's own provenance entry, for the "today" value shown beside a proposal
    entries: dict = field(default_factory=dict, compare=False, hash=False)


def conditions_met(when: dict, parcel: ParcelFacts) -> bool:
    zone = (parcel.zone_class or "").upper()
    patterns = when.get("zone_patterns")
    if patterns and not any(re.search(p, zone) for p in patterns):
        return False
    overlays = set(parcel.overlay_types)
    if when.get("overlays_any") and not overlays & set(when["overlays_any"]):
        return False
    if overlays & set(when.get("overlays_none") or []):
        return False
    if not set(when.get("facts_all") or []) <= parcel.fact_ids:
        return False
    ranges = when.get("address_ranges")
    if ranges and not any(
        currency.map_effect_matches({**r, "kind": "pending_designation"}, parcel.address, overlays) for r in ranges
    ):
        return False
    return True


# Units the Profile's own provenance value omits ("1000"); applied only to a plain number.
_UNITS = {"zoning.min_lot_area_per_unit": "{:,} sq ft", "zoning.unit_yield": "{:,} units by lot area"}


def _scalar(value):
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)


def _shown(fact_id: str, value):
    """The current figure as the Profile words it, so a proposal sits beside the same number."""
    value = _scalar(value)
    template = _UNITS.get(fact_id)
    if template and isinstance(value, (int, float)) and not isinstance(value, bool):
        return template.format(int(value) if float(value).is_integer() else value)
    if template and isinstance(value, str) and value.replace(",", "").isdigit():
        return template.format(int(value.replace(",", "")))
    return value


def _affected(fact_ids: list[str], parcel: ParcelFacts) -> list[PendingTextAffectedFact]:
    out: list[PendingTextAffectedFact] = []
    for fid in fact_ids:
        if fid in NOTE_FACTS:
            label, law = NOTE_FACTS[fid]
            out.append(PendingTextAffectedFact(fact_id=fid, label=label, current_law=law))
        elif fid in parcel.fact_ids:
            entry = parcel.entries.get(fid) or {}
            out.append(PendingTextAffectedFact(
                fact_id=fid, label=entry.get("label") or fid, current_value=_shown(fid, entry.get("value")),
                section=entry.get("section"),
            ))
    return out


def _effect(imp: dict, parcel: ParcelFacts) -> PendingTextEffect | None:
    when = imp.get("applies_when") or {}
    fact_ids = list(imp["fact_ids"])
    plain = [f for f in fact_ids if f not in NOTE_FACTS]
    # The parcel must actually show a fact the proposal could change (or, for a coverage note,
    # sit on the reviewed street segment, which conditions_met checks).
    if plain and not any(f in parcel.fact_ids for f in plain):
        return None
    if not conditions_met(when, parcel):
        return None
    affected = _affected(fact_ids, parcel)
    if not affected:
        return None
    return PendingTextEffect(
        id=imp["id"], sections=[normalize_section(s) for s in imp["sections"]],
        could_change=imp["could_change"], reach=imp["reach"], reach_note=imp.get("reach_note"),
        affected=affected,
    )


def impacts_for(matters: list[PendingText], reviews: dict[str, dict], parcel: ParcelFacts) -> list[PendingTextImpact]:
    """Pending proposals a committed review of the current record maps to this parcel. Tested
    effects first, then those whose reach cannot be tested, newest introduction first."""
    out: list[PendingTextImpact] = []
    for m in matters:
        if review_state(m, reviews) != "reviewed":
            continue
        review = reviews[m.lifecycle_id]
        effects = [e for imp in review["impacts"] if (e := _effect(imp, parcel))]
        if not effects:
            continue
        out.append(PendingTextImpact(
            record_number=m.record_number, lifecycle_id=m.lifecycle_id, title=m.title, status=m.status,
            sub_status=m.sub_status, introduced_at=m.introduced_at, latest_action_at=m.latest_action_at,
            url=m.url, reviewed_on=review["reviewed_on"], reviewed_by=review["reviewed_by"],
            basis="ordinance", summary=review.get("summary"), effects=effects,
        ))
    out.sort(key=lambda i: (all(e.reach == "untested" for e in i.effects), -(
        datetime.fromisoformat(i.introduced_at).timestamp() if i.introduced_at else 0
    ), i.record_number))
    return out


def review_summary(
    matters: list[PendingText], reviews: dict[str, dict], today: date, *, checked_at: str | None, stale: bool,
) -> PendingTextReview:
    waiting = backlog(matters, reviews, today)
    by_record = {m.record_number: m for m in matters}
    ages = [r["waiting_days"] for r in waiting if r["waiting_days"] is not None]
    return PendingTextReview(
        status="incomplete" if waiting else "complete",
        pending_count=len(matters),
        reviewed_count=len(matters) - len(waiting),
        unreviewed=[
            PendingTextUnreviewed(
                record_number=r["record"], title=by_record[r["record"]].title, url=by_record[r["record"]].url,
                introduced_at=by_record[r["record"]].introduced_at, reason=r["reason"], waiting_days=r["waiting_days"],
            )
            for r in waiting
        ],
        oldest_unreviewed_days=max(ages) if ages else None,
        overdue=bool(ages) and max(ages) > REVIEW_WARN_DAYS,
        review_provenance=UpcomingZoningProvenance(
            source_id="internal.pending_impact_review", as_of=checked_at,
            method="Pending Title 17 proposals read by us and mapped to the Profile rules and facts they could change",
            confidence="low" if stale or waiting else "standard",
        ),
    )


def unavailable_review(checked_at: str | None = None) -> PendingTextReview:
    return PendingTextReview(
        status="unavailable",
        review_provenance=UpcomingZoningProvenance(
            source_id="internal.pending_impact_review", as_of=checked_at,
            method="Not available: the pending-legislation snapshot could not be read", confidence="low",
        ),
    )


def for_parcel(
    path: Path | str, *, summary_status: str, checked_at: str | None, parcel: ParcelFacts,
    now: datetime | None = None,
) -> tuple[list[PendingTextImpact], PendingTextReview]:
    """The Profile's pending-text-impact contract from last-good local data.

    An unavailable pending snapshot (or an unreadable store) is ``unavailable``, never an empty
    list that could read as "nothing relevant"."""
    if summary_status == "unavailable":
        return [], unavailable_review(checked_at)
    now = now or datetime.now(timezone.utc)
    try:
        matters = read_text_matters(path)
    except (OSError, sqlite3.Error):
        return [], unavailable_review(checked_at)
    reviews = load_reviews()
    today = now.astimezone(currency.CHICAGO).date()
    review = review_summary(matters, reviews, today, checked_at=checked_at, stale=summary_status == "stale")
    return impacts_for(matters, reviews, parcel), review
