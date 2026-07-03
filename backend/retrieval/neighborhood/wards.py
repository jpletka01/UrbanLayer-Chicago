"""Ward boundaries + alderman contact.

Aldermanic prerogative makes the ward the operative political unit for any
rezoning, variance, or planned-development conversation in Chicago — a parcel
answer without its ward/alderman is missing table-stakes context.

Boundaries: ``p293-wvbd`` (Boundaries - Wards 2023-, 50 multipolygons).
Contacts:   ``htai-wnw4`` (Ward Offices: alderman name, phone, email, website).

Both are preloaded at startup (same pattern as TIF/EZ boundaries) and served
from memory; ``ward_by_point`` is a pure shapely point-in-polygon.
"""

from __future__ import annotations

import logging

import httpx
from shapely.geometry import Point, shape

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

DATASET_WARD_BOUNDARIES = "p293-wvbd"
DATASET_WARD_OFFICES = "htai-wnw4"

_wards: list[tuple[int, object]] | None = None  # (ward_number, shapely geometry)
_offices: dict[int, dict] | None = None


async def preload(*, client: httpx.AsyncClient | None = None) -> None:
    """Fetch ward polygons + office contacts into module memory."""
    global _wards, _offices
    settings = get_settings()

    rows = await socrata_get(
        DATASET_WARD_BOUNDARIES,
        {"$select": "ward,the_geom", "$limit": 100},
        client=client,
        base_url=settings.socrata_base,
        app_token=settings.socrata_app_token or None,
    )
    wards: list[tuple[int, object]] = []
    for row in rows or []:
        try:
            wards.append((int(row["ward"]), shape(row["the_geom"])))
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("Skipping malformed ward row: %s", exc)
    if not wards:
        raise RuntimeError("Ward boundary preload returned no usable polygons")

    offices_rows = await socrata_get(
        DATASET_WARD_OFFICES,
        {"$select": "ward,alderman,ward_phone,email,website", "$limit": 100},
        client=client,
        base_url=settings.socrata_base,
        app_token=settings.socrata_app_token or None,
    )
    offices: dict[int, dict] = {}
    for row in offices_rows or []:
        try:
            # Socrata URL columns arrive as {"url": "..."} objects, not strings.
            website = row.get("website")
            if isinstance(website, dict):
                website = website.get("url")
            offices[int(row["ward"])] = {
                "alderman": row.get("alderman"),
                "phone": row.get("ward_phone"),
                "email": row.get("email"),
                "website": website,
            }
        except (KeyError, TypeError, ValueError):
            continue

    _wards = wards
    _offices = offices
    log.info("Preloaded %d ward polygons, %d ward offices", len(wards), len(offices))


def ward_by_point(lat: float, lon: float) -> dict | None:
    """Return {"ward", "alderman", "phone", "email", "website"} or None.

    None when the point is outside every ward OR the preload never ran —
    ward context degrades silently (it augments, never gates).
    """
    if not _wards:
        return None
    pt = Point(lon, lat)
    for ward_num, geom in _wards:
        try:
            if geom.contains(pt):
                office = (_offices or {}).get(ward_num, {})
                return {
                    "ward": ward_num,
                    "alderman": office.get("alderman"),
                    "phone": office.get("phone"),
                    "email": office.get("email"),
                    "website": office.get("website"),
                }
        except Exception:  # noqa: BLE001 — one bad geometry must not sink the scan
            continue
    return None
