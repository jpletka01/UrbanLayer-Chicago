"""How an address became a parcel, in terms a reader can check.

The Profile used to show a PIN and a green check. The honest picture is richer: which
record matched the address (Cook County Address Points, the Assessor's Parcel
Addresses, a PIN or point the user gave, or only a geocoder), whether several parcels
share the address, whether the two address sources agree, how far the matched point is
from the parcel's center, and whether the identity could not be confirmed. This builds
that record; the Profile shows it and chat states the same line.

``method`` values: ``coordinates`` (a point the user gave), ``pin`` (a PIN the user
gave), ``address_points`` (Cook County Address Points), ``assessor_addresses`` (the
Assessor's Parcel Addresses), ``geocode_nearest`` (only the geocoded point; nearest
parcel, approximate), ``geocode_nearest_verified`` (nearest parcel whose own address
round-trips to the input).
"""

from __future__ import annotations

import math

SOURCES = ("address_points", "assessor_addresses")


def _feet(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 20_902_231  # earth radius in feet
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parcel_centroid(geometry: dict | None) -> tuple[float, float] | None:
    """(lat, lon) of a parcel polygon's centroid, or None when it can't be read."""
    if not geometry:
        return None
    try:
        from shapely.geometry import shape

        c = shape(geometry).centroid
        return (c.y, c.x) if not c.is_empty else None
    except Exception:  # noqa: BLE001 — malformed geometry is absence, not an error
        return None


_POINT_BASIS = {
    "coordinates": "given",
    "pin": "parcel_centroid",
    "address_points": "address_point",
    "assessor_addresses": "parcel_centroid",
    "geocode_nearest": "geocode",
    "geocode_nearest_verified": "geocode",
}


def build_resolution(
    *,
    address: str | None,
    method: str | None,
    lat: float,
    lon: float,
    pin: str | None,
    confidence: str | None,
    ap_pins: list[str] | None = None,
    assessor_pins: list[str] | None = None,
    unverified: bool = False,
    unverified_reason: str | None = None,
    property_pin: str | None = None,
    parcel_geometry: dict | None = None,
) -> dict:
    """The resolution record. ``ap_pins`` / ``assessor_pins`` are every PIN each address
    source lists for the input address (empty when the user gave a PIN or a point)."""
    ap = sorted(set(ap_pins or []))
    asr = sorted(set(assessor_pins or []))
    all_pins = sorted(set(ap) | set(asr) | ({pin} if pin and (ap or asr) else set()))
    candidates = [
        {
            "pin": p,
            "sources": [s for s, pins in (("address_points", ap), ("assessor_addresses", asr)) if p in pins],
            "used": p == pin,
        }
        for p in all_pins
    ]

    # A condominium building: the building's own PIN ends 0000 and each unit has a PIN
    # sharing its first 10 digits with a unit number from 1001 up (P4's tower: one
    # building PIN in Address Points, 50 unit PINs at the Assessor). That is how
    # condos are recorded, not a disagreement between the two sources.
    condo_units = 0
    if pin and pin.endswith("0000"):
        condo_units = sum(1 for p in all_pins if p[:10] == pin[:10] and p != pin and p[10:].isdigit() and int(p[10:]) >= 1001)
    if condo_units < 2:
        condo_units = 0

    centroid = parcel_centroid(parcel_geometry)
    gap = round(_feet(lat, lon, centroid[0], centroid[1])) if centroid else None

    return {
        "method": method,
        "point_basis": _POINT_BASIS.get(method or ""),
        "input_address": address,
        "pin": pin,
        "confidence": confidence,
        "point": {"lat": lat, "lon": lon},
        "centroid_gap_ft": gap,
        "candidates": candidates,
        # Several parcels share this address (a strip center, a condo building)...
        "multiple_parcels": len(all_pins) > 1,
        # ...and the two official address sources can name DIFFERENT parcels for it
        # (a condominium's building PIN vs its unit PINs is not that: see condo_units).
        "sources_disagree": bool(ap and asr and not (set(ap) & set(asr)) and not condo_units),
        # >0 when the matched PIN is a condominium building whose units have their own PINs.
        "condo_units": condo_units,
        "identity_unconfirmed": unverified,
        "unverified_reason": unverified_reason if unverified else None,
        "property_record_pin": property_pin if unverified else None,
    }
