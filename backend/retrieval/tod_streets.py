"""TOD streets (Chicago Zoning Ordinance §17-3-0600), applied ahead of codification.

SO2026-0025391 passed on 2026-10-14 and took effect on passage, but the code text we
serve predates it and the City's zoning map has no TOD layer yet. The segment table and
the rule text below are transcribed from the passed substitute (a 3-page scan, read in
session 2026-10-21; the transcription is committed at
tests/fixtures/ordinances/SO2026-0025391.json and pinned by tests/test_tod_streets.py).
Once the section is codified, the same test asserts the table against the code text.

Matching is by street address (street, direction, number range), the same way the
reviewed ``map_effects`` in code_amendments.json match: a lot that reaches a TOD street
only from a cross street is not caught, and the note says so. A parcel-geometry check is
the follow-up the plan names.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.legislation import currency

RECORD = "SO2026-0025391"
SECTION = "17-3-0600"


@dataclass(frozen=True)
class TodSegment:
    direction: str
    street: str       # as the address parser reads it, upper case, no suffix
    label: str        # how we print it
    frm: int
    to: int
    from_cross: str
    to_cross: str
    suffix: str = "AVE"


# §17-3-0603: "Ravenswood: Irving Park to Lawrence, 4001N-4799N; Western: Addison to Ainslie, 3600N-4859N".
SEGMENTS = (
    TodSegment("N", "RAVENSWOOD", "N Ravenswood Ave", 4001, 4799, "Irving Park Rd", "Lawrence Ave"),
    TodSegment("N", "WESTERN", "N Western Ave", 3600, 4859, "Addison St", "Ainslie St"),
)

# §17-3-0604, in the ordinance's order.
PROHIBITED_USES = (
    "strip centers",
    "drive-through facilities",
    "vehicle sales and service uses involving any outdoor storage of vehicles or goods",
    "gas stations",
    "car washes",
    "residential storage warehouses",
    "electronic data storage centers",
    "motor vehicle repair shops",
)


def _segment_for(address: str | None) -> TodSegment | None:
    parts = currency.address_parts(address)
    if parts is None:
        return None
    number, direction, name = parts
    for seg in SEGMENTS:
        if seg.direction == direction and seg.street == name and seg.frm <= number <= seg.to \
                and not currency.suffix_conflicts(seg.suffix, address):
            return seg
    return None


def tod_street_status(address: str | None) -> dict | None:
    """The TOD-street facts for an address on a TOD segment, else None."""
    seg = _segment_for(address)
    if seg is None:
        return None
    review = currency.load_reviews().get(RECORD) or {}
    codified = review.get("codified") is True
    passed_on = review.get("passed_on")
    return {
        "street": seg.label,
        "segment": f"{seg.from_cross} to {seg.to_cross}",
        "range": f"{seg.frm}–{seg.to} {seg.direction}",
        "record": RECORD,
        "passed_on": passed_on,
        "url": review.get("url"),
        "section": SECTION,
        "codified": codified,
        "prohibited_uses": list(PROHIBITED_USES),
        "rezoning": "a rezoning of abutting property must be to a B or C1 district with a FAR of at least 3 (§17-3-0602-E)",
    }


def tod_street_note(status: dict) -> dict:
    """The coverage note (plain dict, see coverage_notes._note) for a TOD-street parcel."""
    if status["codified"]:
        basis = "under §17-3-0600"
    else:
        when = f" (passed {currency.fmt_day(status['passed_on'])})" if status["passed_on"] else ""
        basis = f"under ordinance {status['record']}{when}, which is not yet in the published code text"
    uses = "; ".join(status["prohibited_uses"][:-1]) + "; and " + status["prohibited_uses"][-1]
    text = (
        f"This address is on {status['street']} ({status['range']}, {status['segment']}), a TOD street {basis}. "
        f"Prohibited on lots abutting a TOD street: {uses} (§17-3-0604). "
        f"Also, {status['rezoning']}, and the pedestrian-street exceptions in §17-3-0308(2) don't apply. "
        "The City's zoning map doesn't show TOD streets yet, and we match by street address, so a lot that "
        "reaches the street only from a cross street isn't caught here. Confirm with the Department of "
        "Planning and Development."
    )
    return {
        "id": "tod_street", "applies": "parcel", "text": text, "ahead_of_code": not status["codified"],
        "params": {"street": status["street"], "record": status["record"], "date": status["passed_on"] or ""},
        "link": status["url"], "section": SECTION,
    }
