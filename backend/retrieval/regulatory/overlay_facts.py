"""Turn a zoning-overlay feature's raw attributes into a name, a plain statement of
what it means, and a link to the source.

The City's overlay layers carry more than the generic layer name the Profile used to
show: the special-district layer names the district ("Predominance of the Block (606)
District") and links its code section, the ADU layer names the zone and lists its
limitations, the Planned Development layer carries the PD number, the landmark layers
name the landmark. Every statement below is pinned to the code text (see
tests/test_overlay_facts.py); where the code doesn't say, the detail stays empty
rather than guessing.
"""

from __future__ import annotations

PD_DOC_URL = "https://gisapps.chicago.gov/gisimages/zoning_pds/PD{num}.pdf"

_LANDMARK_APPROVAL = (
    "a permit to alter, demolish or add to it needs the Commission on Chicago Landmarks' "
    "written approval (§2-120-740)"
)
_LANDMARK_DISTRICT_APPROVAL = (
    "permits to alter or demolish a building, or to build an addition or a new structure on "
    "land in the district, need the Commission on Chicago Landmarks' written approval (§2-120-740)"
)


def _text(v) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s if s and s not in ("0", ".", "None") else None


def _title(s: str) -> str:
    """'NOEL STATE BANK' -> 'Noel State Bank' (leave mixed-case names alone)."""
    return s.title() if s.isupper() else s


def describe_overlay(layer_type: str, attrs: dict) -> dict[str, str | None]:
    """{"name", "detail", "link"} for one overlay feature; any may be None."""
    name = detail = link = None

    if layer_type == "special_district":
        name = _text(attrs.get("SD_NAME"))
        link = _text(attrs.get("LINK"))
        if name and "(606)" in name:
            # §17-7-0591: the district consists of RS-3 and RT-3.5 parcels only.
            detail = (
                "Applies to RS-3 and RT-3.5 parcels only (§17-7-0591); in RS-3 it allows a "
                "two-unit building at 1,500 sq ft of lot per unit (§17-2-0303-B.1). It does not "
                "change the density of other districts."
            )
        elif name:
            detail = "See the linked code section for what this special district requires."

    elif layer_type == "planned_development":
        num = attrs.get("PD_NUM")
        try:
            num = int(float(num)) if num not in (None, "") else None
        except (TypeError, ValueError):
            num = None
        if num:
            name = f"Planned Development {num}"
            link = PD_DOC_URL.format(num=num)
        detail = (
            "Height, floor area and use standards come from the PD ordinance's plan of "
            "development and bulk table, not from Title 17's base-district tables."
        )

    elif layer_type == "landmark_building":
        lm = _text(attrs.get("LANDMARKNAME"))
        name = _title(lm) if lm else None
        detail = f"Individual Chicago Landmark: {_LANDMARK_APPROVAL}."

    elif layer_type in ("historic_district", "landmark_district"):
        nm = _text(attrs.get("NAME"))
        num = _text(attrs.get("NUMBER_"))
        name = f"{_title(nm)} ({num})" if nm and num else (_title(nm) if nm else None)
        # The Historic Districts layer also holds districts that aren't Chicago
        # Landmark districts; only a district the layer flags LANDMARK=Y gets the
        # permit-review statement.
        if layer_type == "landmark_district" or str(attrs.get("LANDMARK") or "").strip().upper() == "Y":
            detail = f"Chicago Landmark district: {_LANDMARK_DISTRICT_APPROVAL}."

    elif layer_type == "adu_area":
        zone = _text(attrs.get("ZONE"))
        limits = _text(attrs.get("TEXT"))
        name = f"ADU-Allowed RS Area — {zone}" if zone else None
        if limits:
            detail = f"Limitations: {limits} (§17-7-0573, §17-7-0574)."

    return {"name": name, "detail": detail, "link": link}
