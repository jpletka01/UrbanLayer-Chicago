"""What the Property Profile does NOT cover, stated per parcel.

A screening page that never says where it stops reads as a determination. These
notes are deterministic (no model): each one is true of THIS parcel or true of every
parcel, cites its source, and names who to ask. ``applies == "parcel"`` notes come from
what the Profile found (a PD, a landmark, a CHRS demolition hold, a recent rezoning, an
ADU zone's limits); ``"general"`` notes apply everywhere (the alderman's role, the
map's lag, the code's vintage, the City's official letter).

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


def build_coverage_notes(
    *,
    zoning,
    regulatory,
    property_,
    neighborhood,
    adu: dict | None,
    code_vintage: dict | None,
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

    if adu and adu.get("status") == "allowed_with_limits" and adu.get("limits"):
        notes.append(_note(
            "adu_limits", "parcel",
            f"Coach houses and conversion units here come with the ADU zone's limitations: {adu['limits']}. "
            "Confirm they are still available before relying on one.",
            params={"zone": adu.get("zone") or ""}, section="17-7-0574",
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
    if code_vintage and code_vintage.get("current_through"):
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
