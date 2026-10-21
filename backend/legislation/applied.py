"""Law passed after the code text's vintage, applied to a parcel ahead of codification
(WS1 M4b; plan Q1). Each rule is a reviewed amendment (``product_effect: applied`` in
backend/code_amendments.json) whose effect reached the parcel; the statement cites the
ordinance and says it is not yet in the published code. Pure and offline, like
``currency``. The notes feed ``coverage_notes`` (Profile, chat), and the report reads
the same ones.

Pedestrian-street changes are map designations. The map's pedestrian-street layer is a
point-in-polygon lookup that returns nothing even on long-standing pedestrian streets
(checked 2026-10-21: Armitage, Belmont 1650 W, Clark 2400 N), so its silence can't tell us
whether the map has caught up. These notes therefore match by address range alone and say
the map "may" lag. A removal stops speaking once the code text carries it.
"""

from __future__ import annotations

from typing import Iterable

from backend.legislation import currency
from backend.retrieval.tod_streets import RECORD as TOD_RECORD, tod_street_note, tod_street_status

SCO_RECORD = "SO2026-0027187"
SCO_NAME = "milwaukee avenue special character overlay"
PEDESTRIAN_STANDARDS = "17-3-0504"


def _applied(record: str) -> dict | None:
    a = currency.load_reviews().get(record)
    if a and a.get("review_status") == "reviewed" and a.get("product_effect") == "applied":
        return a
    return None


def _label(a: dict) -> str:
    return f"{a['record']} (passed {currency.fmt_day(a['passed_on'])})"


def _ped_notes(address: str | None, overlay_types: Iterable[str] = ()) -> list[dict]:
    notes: list[dict] = []
    overlay_types = set(overlay_types)
    for a in currency.load_reviews().values():
        if a.get("review_status") != "reviewed" or a.get("product_effect") != "applied":
            continue
        for e in a.get("map_effects") or []:
            kind = e.get("kind")
            if kind not in ("pedestrian_street_added", "pedestrian_street_removed"):
                continue
            if e.get("from") is None or e.get("to") is None or not currency.map_effect_matches(e, address, overlay_types):
                continue
            street = f"{e['direction']} {e['street'].title()}"
            span = f"{e['from']}–{e['to']} {e['direction']}"
            ahead = a.get("codified") is not True
            where = "not yet in the published code text" if ahead else "now in §17-3-0503-D"
            if kind == "pedestrian_street_added":
                # Kept after codification too: the page's overlay lookup rarely detects pedestrian streets,
                # so this note is how the Profile says the lot abuts one.
                notes.append({
                    "id": "pedestrian_street_added", "applies": "parcel", "ahead_of_code": ahead,
                    "text": (
                        f"{span} {e['street'].title()} was designated a pedestrian retail street by ordinance {_label(a)}, {where}; "
                        "the City's zoning map may not show it yet. Lots abutting a pedestrian street follow the standards in "
                        f"§{PEDESTRIAN_STANDARDS}: the building at the sidewalk, 60% ground-floor windows, an entrance facing the "
                        "street, no curb cuts, and no strip centers, drive-through facilities, gas stations or car washes. "
                        "We match by street address; confirm with the Department of Planning and Development."
                    ),
                    "params": {"street": street, "range": span, "record": a["record"], "date": a["passed_on"]},
                    "link": a.get("url"), "section": PEDESTRIAN_STANDARDS,
                })
            elif ahead:
                notes.append({
                    "id": "pedestrian_street_removed", "applies": "parcel", "ahead_of_code": True,
                    "text": (
                        f"Ordinance {_label(a)} removed the pedestrian-street designation from {span} {e['street'].title()}, "
                        f"{where}, and the City's zoning map may still show it. The pedestrian-street standards in "
                        f"§{PEDESTRIAN_STANDARDS} no longer apply to this lot. "
                        "We match by street address; confirm with the Department of Planning and Development."
                    ),
                    "params": {"street": street, "range": span, "record": a["record"], "date": a["passed_on"]},
                    "link": a.get("url"), "section": PEDESTRIAN_STANDARDS,
                })
    return notes


def pedestrian_street_removed(address: str | None, overlay_types: Iterable[str]) -> bool:
    """True when a passed ordinance de-designated the pedestrian street this address
    sits on and the code text doesn't carry that yet (the report then drops its
    pedestrian-street opportunity)."""
    return any(n["id"] == "pedestrian_street_removed" for n in _ped_notes(address, overlay_types))


def _sco_note(overlay_names: Iterable[str]) -> dict | None:
    a = _applied(SCO_RECORD)
    if a is None or a.get("codified") is True:
        return None
    if not any(SCO_NAME in (n or "").lower() for n in overlay_names):
        return None
    return {
        "id": "milwaukee_sco_strip_centers", "applies": "parcel", "ahead_of_code": True,
        "text": (
            "This parcel is in the Milwaukee Avenue Special Character Overlay District, which prohibits strip centers, "
            "drive-through facilities, vehicle sales and service with outdoor storage or car washes, gas stations and "
            f"residential storage warehouses (§17-7-1506). Ordinance {_label(a)}, not yet in the published code text, "
            "excepts a strip center that is the adaptive reuse or rehabilitation of an existing building."
        ),
        "params": {"record": a["record"], "date": a["passed_on"]},
        "link": a.get("url"), "section": "17-7-1506",
    }


def applied_law_notes(address: str | None, overlays: Iterable = ()) -> list[dict]:
    """Coverage notes for law applied ahead of codification that reaches this parcel."""
    overlays = list(overlays)
    types = {getattr(o, "layer_type", None) for o in overlays}
    notes: list[dict] = []
    if _applied(TOD_RECORD) is not None:
        status = tod_street_status(address)
        if status:
            notes.append(tod_street_note(status))
    notes += _ped_notes(address, types)
    sco = _sco_note([getattr(o, "name", None) for o in overlays if getattr(o, "layer_type", None) == "special_district"])
    if sco:
        notes.append(sco)
    return notes

