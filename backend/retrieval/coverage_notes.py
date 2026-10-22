"""What the Property Profile does NOT cover, stated per parcel.

A screening page that never says where it stops reads as a determination. These
notes are deterministic (no model): each one is true of THIS parcel or true of every
parcel, cites its source, and names who to ask. ``applies == "parcel"`` notes come from
what the Profile found (a PD, a landmark, a CHRS demolition hold, a recent rezoning, an
ADU zone's limits); ``"general"`` notes apply everywhere (the alderman's role, the
map's lag, the code's vintage and the amendments passed since, the City's official letter).

Each note carries a stable ``id`` and ``params`` (the frontend translates those) and an
English ``text`` (what chat restates). Statements are pinned to the ingested code in
tests/test_coverage_notes.py; the letter's fee and timing are the Office of the Zoning
Administrator's published terms, checked 2026-09-30.
"""

from __future__ import annotations

# The Office of the Zoning Administrator's published terms (chicago.gov), checked 2026-09-30.
OFFICIAL_LETTER_URL = "https://www.chicago.gov/city/en/depts/dcd/supp_info/office_of_the_zoningadministrator.html"
OFFICIAL_LETTER_FEE = 150
OFFICIAL_LETTER_DAYS = 30
OFFICIAL_LETTER_CHECKED = "2026-09-30"


def _note(id_: str, applies: str, text: str, *, params: dict | None = None, link: str | None = None, section: str | None = None) -> dict:
    return {"id": id_, "applies": applies, "text": text, "params": params or {}, "link": link, "section": section}


def landmark_designation_text(hit: dict) -> str:
    """The sentence for one passed designation that lists this parcel. A district names blocks, and its boundary
    is in the ordinance text, so for a district we say the address is on a block the title names and that this
    page cannot say whether the parcel is inside it. When the landmark layers did not answer, we do not claim
    the map doesn't show it."""
    from backend.legislation.currency import fmt_day

    what = f"{hit['name']} ({hit['record']})" if hit.get("name") and hit["name"].lower() != "building" else hit["record"]
    if hit.get("kind") == "district":
        listed = (f"A Chicago Landmark district designation ordinance, {what}, passed City Council on {fmt_day(hit['passed_on'])} "
                  f"and names the blocks of {hit.get('segment') or 'this street'}, which include this address. The ordinance sets "
                  "the district's boundary, so this page cannot say whether this parcel is inside it.")
    else:
        listed = (f"A Chicago Landmark designation ordinance listing this address, {what}, passed City Council on "
                  f"{fmt_day(hit['passed_on'])}.")
    if hit.get("map_checked", True):
        map_part = " The City's landmark map did not show this parcel as a landmark when we checked, so the overlays on this page may be missing a review requirement."
    else:
        map_part = " The City's landmark map could not be checked today, so the overlays on this page may be missing a review requirement."
    return (listed + map_part + " Alterations, demolition and new construction on a designated Chicago Landmark need the Commission on "
            "Chicago Landmarks' written approval before a permit can issue (§2-120-740). Confirm with the Department of "
            "Planning and Development.")


def build_coverage_notes(
    *,
    zoning,
    regulatory,
    property_,
    neighborhood,
    adu: dict | None,
    code_vintage: dict | None,
    code_currency: dict | None = None,
    address: str | None = None,
    passed_not_on_map: list[dict] | None = None,
    passed_landmark_designations: list[dict] | None = None,
) -> list[dict]:
    """The ordered list of notes for one parcel. Every argument may be None."""
    notes: list[dict] = []
    overlays = list(getattr(regulatory, "overlays", None) or [])
    by_type = {o.layer_type: o for o in overlays}

    # --- true of THIS parcel -------------------------------------------------------------
    pd = by_type.get("planned_development")
    zone = (getattr(zoning, "zone_class", "") or "").upper()
    if pd is not None or zone.startswith("PD"):
        name = (pd.name if pd and pd.name else None) or zone or "a Planned Development"
        notes.append(_note(
            "planned_development", "parcel",
            f"This parcel is in {name}. Its height, floor area and use standards are set by the PD ordinance and its "
            "bulk table, not by Title 17's base-district tables; the base-district numbers on this page do not apply to it.",
            params={"name": name}, link=pd.link if pd else None,
        ))

    landmark = next((by_type[t] for t in ("landmark_building", "landmark_district", "historic_district")
                     if t in by_type and "2-120-740" in (by_type[t].detail or "")), None)
    if landmark is not None:
        notes.append(_note(
            "landmark", "parcel",
            f"{landmark.name or 'This property'} is a Chicago Landmark or in a landmark district: a permit to alter, "
            "demolish or build needs the Commission on Chicago Landmarks' written approval (§2-120-740). "
            "This page does not assess that review.",
            params={"name": landmark.name or ""}, section="2-120-740",
        ))

    chrs = (getattr(getattr(property_, "flags", None), "chrs_rating", None) or "").lower()
    if chrs in ("orange", "red") and landmark is None:
        notes.append(_note(
            "chrs_demolition_delay", "parcel",
            f"The Chicago Historic Resources Survey color-codes this building {chrs}: a demolition permit may be held "
            "for up to 90 days so the Department of Planning and Development can explore preserving it (§14A-4-407.6).",
            params={"color": chrs}, section="14A-4-407.6",
        ))

    if zoning is not None and getattr(zoning, "recently_rezoned", False) and getattr(zoning, "ordinance_date", None):
        notes.append(_note(
            "recently_rezoned", "parcel",
            f"This district was changed by an ordinance dated {zoning.ordinance_date}. The City's map can lag a passed "
            "amendment by up to 90 days, so confirm the current district with the Department of Planning and Development.",
            params={"date": zoning.ordinance_date, "ordinance": getattr(zoning, "ordinance_num", None) or ""},
            link=getattr(zoning, "clerk_url", None),
        ))

    # A rezoning that lists this address passed but the City's map hasn't been updated (WS1 M5):
    # the district on this page is the old one. Says what we know (a listing), not what it changes.
    for hit in passed_not_on_map or []:
        from backend.legislation.currency import fmt_day

        notes.append(_note(
            "passed_not_on_map", "parcel",
            f"A rezoning ordinance listing this address passed City Council on {fmt_day(hit['passed_on'])} "
            f"({hit['record']}). The City's zoning map, which this page's district comes from, has not been updated "
            "for it yet, so the standards on this page are for the district the map still shows. Confirm the current "
            "district with the Department of Planning and Development.",
            params={"date": hit["passed_on"], "record": hit["record"], "segment": hit.get("segment") or ""},
            link=hit.get("url"),
        ))

    # A landmark designation that lists this address passed but the City's landmark map doesn't show the parcel
    # yet (WS1 M5b). Says what we know (the ordinance lists this address or block), never that the parcel is a landmark.
    for hit in passed_landmark_designations or []:
        notes.append(_note(
            "landmark_designation_passed", "parcel", landmark_designation_text(hit),
            params={"date": hit["passed_on"], "record": hit["record"], "name": hit.get("name") or "",
                    "segment": hit.get("segment") or "", "kind": hit.get("kind") or "building"},
            link=hit.get("url"), section="2-120-740",
        ))

    if adu and adu.get("status") == "allowed_with_limits" and adu.get("limits"):
        notes.append(_note(
            "adu_limits", "parcel",
            f"Coach houses and conversion units here come with the ADU zone's limitations: {adu['limits']}. "
            "Confirm they are still available before relying on one.",
            params={"zone": adu.get("zone") or ""}, section="17-7-0574",
        ))

    # Law passed after the code text and applied here ahead of codification (WS1 M4b): TOD streets,
    # pedestrian-street changes the map doesn't show yet, the Milwaukee Ave overlay's strip-center exception.
    from backend.legislation.applied import applied_law_notes

    notes += applied_law_notes(address, overlays)

    # What's left is parcel-relevant but not applied: said to be missing from this page.
    relevant = [
        a for a in (code_currency or {}).get("amendments") or []
        if a.get("parcel_relevant") and not (a.get("review_status") == "reviewed" and a.get("product_effect") == "applied")
    ]
    if relevant:
        from backend.legislation.currency import fmt_day

        items = "; ".join(f"{a['record']} ({fmt_day(a['passed_on'])}): {a.get('summary') or a['title']}" for a in relevant)
        notes.append(_note(
            "code_amendments_parcel", "parcel",
            f"City Council has passed {'amendments' if len(relevant) > 1 else 'an amendment'} since this code text "
            f"was published that may affect this parcel, and {'they are' if len(relevant) > 1 else 'it is'} not "
            f"reflected on this page: {items}.",
            params={"count": len(relevant), "records": [a["record"] for a in relevant]},
            link=relevant[0].get("url"),
        ))

    # --- true of every parcel -----------------------------------------------------------------
    ward = getattr(neighborhood, "ward", None)
    who = ""
    if ward is not None:
        who = f" Ward {ward.ward}" + (f": Ald. {ward.alderman}" if ward.alderman else "") + (f", {ward.phone}" if ward.phone else "") + "."
    notes.append(_note(
        "aldermanic", "general",
        "Zoning map amendments, Planned Developments, special uses and administrative adjustments require notice to the "
        "alderman of the ward (§17-13-0100, §17-13-0300, §17-13-0600), and whether a project is approved turns on "
        "discretionary approvals this page cannot assess." + who,
        params={"ward": ward.ward if ward else None, "alderman": (ward.alderman if ward else None) or "", "phone": (ward.phone if ward else None) or ""},
        link=getattr(ward, "website", None) if ward else None, section="17-13-0300",
    ))
    notes.append(_note(
        "map_lag", "general",
        "The City's zoning map can lag a passed amendment by up to 90 days.",
    ))
    if code_currency and code_currency.get("current_through"):
        from backend.legislation.currency import currency_sentence

        since = code_currency.get("since")
        notes.append(_note(
            "code_currency", "general", currency_sentence(code_currency),
            params={
                "date": code_currency["current_through"], "label": code_currency.get("label") or "",
                "count": since.get("title17") if since else None, "checked": code_currency.get("checked_at"),
                "state": code_currency.get("check_state"),
            },
            link=None if since else code_currency.get("clerk_url"),
        ))
    elif code_vintage and code_vintage.get("current_through"):
        notes.append(_note(
            "code_vintage", "general",
            f"The Municipal Code text used here is current through {code_vintage['current_through']}; a later Council "
            "amendment may not be reflected.",
            params={"date": code_vintage["current_through"]},
        ))
    notes.append(_note(
        "official_letter", "general",
        "This page is a screening tool, not a zoning determination. The City's Zoning Verification Letter confirms a "
        f"parcel's zoning (${OFFICIAL_LETTER_FEE}, up to {OFFICIAL_LETTER_DAYS} days, as published by the Office of the "
        f"Zoning Administrator, checked {OFFICIAL_LETTER_CHECKED}); a letter of opinion covers a specific project.",
        params={"fee": OFFICIAL_LETTER_FEE, "days": OFFICIAL_LETTER_DAYS, "checked": OFFICIAL_LETTER_CHECKED},
        link=OFFICIAL_LETTER_URL,
    ))
    return notes
