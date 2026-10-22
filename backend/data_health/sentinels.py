"""Daily sentinels: do the production lookups still agree with the answer key? (WS6 M4, plan §3.6)

Each day the checker runs the *production* zoning and overlay lookups (``lookup_zoning``,
``query_overlays_checked``) at the coordinates of the 12 parcels in ``eval/kit/parcels.json`` (plus a
positive control: a designated individual landmark, which the kit has none of) and compares what comes
back with the key: the district (field A) and the overlay set (field D). No model, no node, no kit run.

This is the check that would have caught F8 (2026-10-02): the code read the survey's layer 7 as "landmark
building", so P11 (3500 N Lake Shore Dr) came back a landmark. The sentinel derives the overlay set the
way production does, finds ``landmark_building`` where the key says there is none, and alarms.

A mismatch is one of two things, and the alarm text says which fields differ so a person can tell:
the City changed the data (review the key and re-generate) or our code reads it wrongly (fix the code).
It is never re-baselined automatically.

``eval/`` is not in the image, so ``sentinels.json`` is generated from the kit and committed; a test keeps
the two in sync. Coordinates are resolved once, from Address Points, at generation time.

    python -m backend.data_health.sentinels --from-kit eval/kit/parcels.json --control "5749 W Race Ave"
    python -m backend.data_health.sentinels --from-kit eval/kit/parcels.json --control "5749 W Race Ave" --write
    python -m backend.data_health.sentinels --check            # run the sentinels once, print the findings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from backend.data_health.evaluate import Finding

SENTINELS_PATH = Path(__file__).with_name("sentinels.json")

# The key names overlays the way the kit reads (D.expected); production names them by layer type.
KEY_TO_LAYER_TYPE = {
    "tod": "tod_cta", "pd": "planned_development", "lakefront": "lakefront_protection",
    "special_district": "special_district", "adu": "adu_area", "aro": "aro_zone", "ssa": "ssa",
    "national_register": "national_register", "historic_district": "historic_district",
    "landmark_building": "landmark_building", "pedestrian_street": "pedestrian_street", "pmd": "pmd_subarea",
}
LANDMARK_TYPES = frozenset({"landmark_building", "historic_district"})
# Overlay types the key does not curate, so finding one the key doesn't list is not a mismatch: layer 17 covers most
# of the city ("Zone 1, no limitations") and the key encodes ADU through field F (coach house) for RS districts only;
# the key's "tod" is the CTA layer, and Metra TOD (layer 24) is not listed. A key-listed overlay still must be found.
UNCURATED_EXTRA = frozenset({"adu_area", "tod_metra"})


@dataclass(frozen=True)
class Sentinel:
    id: str
    address: str
    pin: str | None
    lat: float
    lon: float
    district: str
    overlays: tuple[str, ...]            # production layer types, sorted
    control: bool = False
    basis: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Sentinel":
        return cls(id=d["id"], address=d["address"], pin=d.get("pin"), lat=float(d["lat"]), lon=float(d["lon"]),
                   district=d["district"], overlays=tuple(sorted(d["overlays"])), control=bool(d.get("control")),
                   basis=d.get("basis", ""))

    def as_dict(self) -> dict:
        return {"id": self.id, "address": self.address, "pin": self.pin, "lat": self.lat, "lon": self.lon,
                "district": self.district, "overlays": list(self.overlays), "control": self.control, "basis": self.basis}


def load_sentinels(path: Path | None = None) -> list[Sentinel]:
    data = json.loads((path or SENTINELS_PATH).read_text())
    return [Sentinel.from_dict(d) for d in data["sentinels"]]


# --- pure comparison --------------------------------------------------------------------------------

def overlay_types(hits: Iterable[tuple[int, dict]], layer_types: dict[int, str]) -> set[str]:
    """The overlay types production derives from layer hits. ``layer_types``: layer id -> type (production's
    ``OVERLAY_LAYERS`` mapping; a test passes the pre-F8 mapping to replay the incident)."""
    return {layer_types[lid] for lid, _ in hits if lid in layer_types}


def _norm_district(z: str | None) -> str:
    return " ".join((z or "").upper().split())


def compare_district(s: Sentinel, zone_class: str | None) -> list[Finding]:
    if _norm_district(zone_class) != _norm_district(s.district):
        return [Finding("alarm", f"{s.id} {s.address}: district is {zone_class or 'none'}, key says {s.district}")]
    return []


def compare_overlays(s: Sentinel, types: set[str]) -> list[Finding]:
    out: list[Finding] = []
    want = set(s.overlays)
    extra, missing = sorted(types - want - UNCURATED_EXTRA), sorted(want - types)
    if extra:
        landmark = [t for t in extra if t in LANDMARK_TYPES]
        why = (" (a landmark the key says this parcel is not: check which layer production reads, F8)"
               if landmark else "")
        out.append(Finding("alarm", f"{s.id} {s.address}: overlay(s) {', '.join(extra)} found, not in the key{why}"))
    if missing:
        out.append(Finding("alarm", f"{s.id} {s.address}: key overlay(s) {', '.join(missing)} not found"))
    return out


def compare(s: Sentinel, zone_class: str | None, types: set[str]) -> list[Finding]:
    """Findings for one parcel: the district, then the overlay set. Everything is an ``alarm``: the key was
    built from primary sources, so a difference is a data change to review or a bug to fix."""
    return compare_district(s, zone_class) + compare_overlays(s, types)


# --- running them ------------------------------------------------------------------------------------

@dataclass
class SentinelRun:
    findings: list[Finding] = field(default_factory=list)
    checked: int = 0
    green: int = 0
    unchecked: list[str] = field(default_factory=list)
    requests: int = 0


async def run_sentinels(sentinels: list[Sentinel], *, lookup=None, overlays=None, concurrency: int = 4) -> SentinelRun:
    """Run the production lookups at each sentinel. ``lookup``/``overlays`` default to production's
    ``lookup_zoning`` and ``query_overlays_checked`` (tests pass fakes)."""
    from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS, query_overlays_checked
    from backend.retrieval.zoning import lookup_zoning

    lookup = lookup or lookup_zoning
    overlays = overlays or query_overlays_checked
    sem = asyncio.Semaphore(concurrency)
    run = SentinelRun()

    async def one(s: Sentinel):
        async with sem:
            try:
                z = await lookup(s.lat, s.lon)
                ov = await overlays(s.lat, s.lon)
            except Exception as exc:
                return s, None, None, f"{type(exc).__name__}: {exc}"
        return s, z, ov, None

    for s, z, ov, err in await asyncio.gather(*(one(s) for s in sentinels)):
        if err or ov is None:
            run.unchecked.append(f"{s.id} ({err})")
            continue
        run.checked += 1
        failed = list(getattr(ov, "failed", []) or [])
        types = overlay_types(ov.hits, OVERLAY_LAYERS_TYPES(OVERLAY_LAYERS))
        # A layer that could not be read says nothing about the overlays, so only the district is judged then.
        found = compare_district(s, (z or {}).get("zone_class")) + ([] if failed else compare_overlays(s, types))
        if failed:
            run.unchecked.append(f"{s.id} (overlay layer(s) {', '.join(map(str, failed))} could not be read)")
        run.findings += found
        if not found and not failed:
            run.green += 1
    return run


def OVERLAY_LAYERS_TYPES(layers: dict[int, dict[str, str]]) -> dict[int, str]:
    return {lid: meta["type"] for lid, meta in layers.items()}


# --- generator ---------------------------------------------------------------------------------------

def _key_overlays(expected: list[str]) -> tuple[str, ...]:
    unknown = [e for e in expected if e not in KEY_TO_LAYER_TYPE]
    if unknown:
        raise SystemExit(f"kit overlay name(s) {unknown} have no production layer type: add them to KEY_TO_LAYER_TYPE")
    return tuple(sorted(KEY_TO_LAYER_TYPE[e] for e in expected))


async def _centroid(pin: str) -> tuple[float, float] | None:
    """The Assessor's parcel centroid (Parcel Universe ``lat``/``lon``): what the key's field A is judged at
    ("the City zoning layer at the Assessor centroid"), and the only point a vacant lot has (P2)."""
    from backend.config import get_settings
    from backend.retrieval.socrata import socrata_get

    st = get_settings()
    rows = await socrata_get(
        st.dataset_parcel_universe if hasattr(st, "dataset_parcel_universe") else "pabr-t5kh",
        {"$where": f"pin='{pin}'", "$select": "lat,lon", "$order": "year DESC", "$limit": 1},
        base_url=st.cook_county_socrata_base, app_token=st.cook_county_socrata_token or None,
    )
    try:
        return float(rows[0]["lat"]), float(rows[0]["lon"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


async def generate(kit_path: Path, control_address: str | None = None) -> dict:
    """Build the sentinel list from the kit key. The control's district and overlays are what production
    returns now, to be reviewed by a person against the official landmark list before committing."""
    from backend.retrieval.property.address_points import address_to_pin

    kit = json.loads(kit_path.read_text())
    out: list[Sentinel] = []
    for p in kit["parcels"]:
        pin = p.get("pin")
        # The point the Profile itself resolves an address to: Address Points' lat/long, when it is unique and
        # is this parcel. A vacant lot (P2) has no address point, so it falls back to the Assessor centroid.
        r = await address_to_pin(p["address"])
        if r and (not pin or r["pin14"] == pin):
            pin, point = pin or r["pin14"], (r["lat"], r["lon"])
        else:
            point = await _centroid(pin) if pin else None
            if point is None:
                raise SystemExit(f"{p['id']} {p['address']}: no matching Address Points point and no centroid; add coordinates by hand")
        out.append(Sentinel(id=p["id"], address=p["address"], pin=pin, lat=point[0], lon=point[1],
                            district=p["A"]["district"], overlays=_key_overlays(p["D"]["expected"]),
                            basis=p["A"].get("basis", "")))
    if control_address:
        from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS, query_overlays_checked
        from backend.retrieval.zoning import lookup_zoning

        r = await address_to_pin(control_address)
        if not r:
            raise SystemExit(f"control {control_address}: no Address Points match")
        z = await lookup_zoning(r["lat"], r["lon"])
        ov = await query_overlays_checked(r["lat"], r["lon"])
        types = overlay_types(ov.hits, OVERLAY_LAYERS_TYPES(OVERLAY_LAYERS))
        if "landmark_building" not in types:
            raise SystemExit(f"control {control_address}: layer 5 (Landmark Boundaries) does not cover it; pick another")
        out.append(Sentinel(id="C1", address=control_address, pin=r["pin14"], lat=r["lat"], lon=r["lon"],
                            district=(z or {}).get("zone_class", ""), overlays=tuple(sorted(types)), control=True,
                            basis="Positive control: a designated individual Chicago Landmark (official list "
                                  "data.cityofchicago.org tdab-kixi; layer 5 covers it). Review before committing."))
    return {"kit_version": kit.get("version"), "kit_code_current_through": kit.get("code_current_through"),
            "sentinels": [s.as_dict() for s in out]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-kit", type=Path, help="eval/kit/parcels.json")
    ap.add_argument("--control", help="address of a designated individual landmark")
    ap.add_argument("--write", action="store_true", help=f"write {SENTINELS_PATH.name}")
    ap.add_argument("--check", action="store_true", help="run the committed sentinels against the live services")
    args = ap.parse_args(argv)
    if args.check:
        run = asyncio.run(run_sentinels(load_sentinels()))
        print(f"{run.green} of {run.checked} checked sentinels match the key; {len(run.unchecked)} could not be checked")
        for f in run.findings:
            print(f"  ALARM {f.text}")
        for u in run.unchecked:
            print(f"  unchecked {u}")
        return 1 if run.findings else 0
    if not args.from_kit:
        ap.error("pass --from-kit or --check")
    data = asyncio.run(generate(args.from_kit, args.control))
    text = json.dumps(data, indent=1) + "\n"
    if args.write:
        SENTINELS_PATH.write_text(text)
        print(f"wrote {len(data['sentinels'])} sentinels to {SENTINELS_PATH}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
