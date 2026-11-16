"""Chicago's rail lines (decision Item 128): drawn on the new UI's base map, and measured once against every lot.

Two government sources, kept side by side in ``backend/data/map_sources/``:

* **CTA 'L' lines**, City of Chicago ``xbyr-jnvx`` (``cta_lines.json``): 153 segments, "Elevated or At Grade" or
  "Subway", with the lines they carry ("Brown Line"). The City draws them "approximately"; where CMAP 2023 has rail
  land they sit a median 5 ft from it (``eval/rail_land.py``).
* **North American Rail Network lines** (``narn_lines.geojson``): the FRA's network in USDOT/BTS's National
  Transportation Atlas Database, public domain (17 U.S.C. § 101). Metra (NIRC/METX), Amtrak and the freight railroads,
  with owner, trackage rights and passenger service. Kept: main/other lines and sidings, yards, industry spurs;
  abandoned (A), trail (T), out of service (X, incl. The 606) and rail-banked (R) are left out.

A line alone never marks a lot as rail land: the owner's blind check found the CTA line alone right on 3 of 8 lots and
the federal line on 2 of 5 (the approximate lines clip the lots beside the tracks). Rail land is CMAP's rail
right-of-way (``lot_facts.mark_land_use``); the CTA line only tells rail from road where CMAP calls an L right-of-way
"road" (6 of 6 were rail and expressway).

    PYTHONPATH=. python -m backend.map_tiles.rail_lines [--out backend/data/map_sources]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

CTA_DATASET = "xbyr-jnvx"
NARN_URL = ("https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
            "NTAD_North_American_Rail_Network_Lines/FeatureServer/0/query")
NARN_FIELDS = "FRAARCID,RROWNER1,RROWNER2,TRKRGHTS1,TRKRGHTS2,TRKRGHTS3,PASSNGR,NET,TRACKS,YARDNAME,SUBDIV"
NARN_ACTIVE = {"M": "main", "O": "main", "S": "main", "Y": "yard", "I": "industry"}
CHICAGO_BBOX = (-87.94, 41.64, -87.52, 42.03)
MIN_CTA, MIN_NARN = 100, 1_500  # 153 and 2,203 on 2026-11-13: fewer is a partial read
CTA_FILE, NARN_FILE, META_FILE = "cta_lines.json", "narn_lines.geojson", "rail_meta.json"
METRA = ("NIRC", "METX", "NICD")  # Metra's own lines and the South Shore (NICTD)

# A local flat projection in feet (Chicago is small: under 0.1% error), for line lengths inside lots.
_LAT0 = 41.85
_FT_PER_DEG_LAT = 364_000.0
_FT_PER_DEG_LON = _FT_PER_DEG_LAT * float(np.cos(np.radians(_LAT0)))


def to_feet(g):
    return shapely.transform(g, lambda xy: np.column_stack([(xy[:, 0] + 87.65) * _FT_PER_DEG_LON,
                                                            (xy[:, 1] - _LAT0) * _FT_PER_DEG_LAT]))


def _get(client: httpx.Client, url: str, params: dict) -> httpx.Response:
    for attempt in range(5):
        try:
            r = client.get(url, params=params)
            if r.status_code < 500:
                r.raise_for_status()
                return r
        except httpx.TransportError:
            if attempt == 4:
                raise
        time.sleep(2 ** attempt)
    r.raise_for_status()
    return r


def fetch(out: Path, *, token: str = "") -> dict:
    """Both sources into ``out`` (atomically per file). A short read raises: the map never draws a partial network."""
    out.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "urbanlayer-map/1.0"} | ({"X-App-Token": token} if token else {})
    with httpx.Client(timeout=120, headers=headers) as c:
        cta = _get(c, f"https://data.cityofchicago.org/resource/{CTA_DATASET}.json", {"$limit": 5000}).json()
        if len(cta) < MIN_CTA:
            raise RuntimeError(f"CTA lines: only {len(cta)} rows")
        feats: list[dict] = []
        while True:
            page = _get(c, NARN_URL, {
                "where": "1=1", "geometry": ",".join(map(str, CHICAGO_BBOX)), "geometryType": "esriGeometryEnvelope",
                "inSR": 4326, "outSR": 4326, "outFields": NARN_FIELDS, "resultOffset": len(feats),
                "resultRecordCount": 2000, "f": "geojson"}).json()
            batch = page.get("features")
            if batch is None:  # ArcGIS answers a failed query with 200 and an error body
                raise RuntimeError(f"NARN answered without features: {str(page)[:200]}")
            feats += batch
            if len(batch) < 2000:
                break
        if len(feats) < MIN_NARN:
            raise RuntimeError(f"NARN lines: only {len(feats)} in Chicago's box")
    meta = {"fetched": time.strftime("%Y-%m-%d"), "cta_rows": len(cta), "narn_rows": len(feats),
            "cta_dataset": CTA_DATASET, "narn_url": NARN_URL}
    for name, body in ((CTA_FILE, cta), (NARN_FILE, {"type": "FeatureCollection", "features": feats}),
                       (META_FILE, meta)):
        tmp = out / f".{name}.part"
        tmp.write_text(json.dumps(body))
        tmp.replace(out / name)
    return meta


def present(folder: Path) -> bool:
    return all((folder / f).exists() and (folder / f).stat().st_size for f in (CTA_FILE, NARN_FILE))


def cta_name(lines: str | None) -> str:
    """'Brown, Purple' / 'Brown Line' → 'Brown, Purple' / 'Brown Line', with the City's '(Exp)' spelled out."""
    s = (lines or "").strip().replace("(Exp)", "(Express)")
    return s


def narn_kind(p: dict) -> str | None:
    """The map's kind for one NARN segment: yard, spur, amtrak, metra or freight; None = not drawn."""
    net = NARN_ACTIVE.get((p.get("NET") or "").strip())
    if net is None:
        return None
    if net == "yard":
        return "yard"
    if net == "industry":
        return "spur"
    owners = {(p.get(k) or "").strip() for k in ("RROWNER1", "RROWNER2", "TRKRGHTS1", "TRKRGHTS2", "TRKRGHTS3")}
    if (p.get("PASSNGR") or "") in ("C", "B") or owners & set(METRA):
        return "metra"
    if (p.get("PASSNGR") or "") == "A" or "AMTK" in owners:
        return "amtrak"
    return "freight"


def load(folder: Path) -> list[tuple[str, object, dict]]:
    """Every drawn line: (kind, lon/lat geometry, props). Kinds: cta (elevated or at grade), cta_subway, metra,
    amtrak, freight, yard, spur. ``props`` has ``name`` for CTA lines."""
    out: list[tuple[str, object, dict]] = []
    for r in json.loads((folder / CTA_FILE).read_text()):
        if not r.get("the_geom"):
            continue
        sub = (r.get("type") or "").lower().startswith("subway")
        out.append(("cta_subway" if sub else "cta", shape(r["the_geom"]), {"name": cta_name(r.get("lines"))}))
    for f in json.loads((folder / NARN_FILE).read_text())["features"]:
        kind = narn_kind(f.get("properties") or {})
        if kind and f.get("geometry"):
            out.append((kind, shape(f["geometry"]), {}))
    return out


def cta_on_lots(folder: Path, pins: list[str], lots: list) -> list[tuple[str, float]]:
    """(pin10, feet of CTA elevated / at-grade line inside the lot) for every lot a line runs through."""
    gs = np.array([to_feet(g) for kind, g, _ in load(folder) if kind == "cta"], dtype=object)
    lots_ft = np.array([to_feet(g) for g in lots], dtype=object)
    li, gi = STRtree(lots_ft).query(gs, predicate="intersects")[::-1]
    acc: dict[int, float] = {}
    for a, b in zip(li, gi):
        acc[int(a)] = acc.get(int(a), 0.0) + float(lots_ft[a].intersection(gs[b]).length)
    return [(pins[a], round(ft, 1)) for a, ft in acc.items() if ft > 0]


def main() -> None:
    from backend.config import get_settings

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="default: map_sources/ beside the base tiles")
    a = ap.parse_args()
    out = a.out or get_settings().map_base_tiles_path.parent / "map_sources"
    print(json.dumps(fetch(out, token=get_settings().socrata_app_token), indent=1))


if __name__ == "__main__":
    main()
