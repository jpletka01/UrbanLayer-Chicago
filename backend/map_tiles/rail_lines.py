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
METRA_FILE = "metra_lines.geojson"
METRA_GTFS_URL = "https://schedules.metrarail.com/gtfs/schedule.zip"
MIN_METRA_ROUTES = 8  # 11 lines on 2026-11-16
# The L's lines in the order they sit side by side where several share a track (the Loop, the north trunk).
CTA_LINES = (("Red", "RD"), ("Blue", "BL"), ("Brown", "BR"), ("Green", "GR"), ("Orange", "OR"), ("Pink", "PK"),
             ("Purple", "PR"), ("Yellow", "YL"))
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
        metra = metra_from_gtfs(_get(c, METRA_GTFS_URL, {}).content)
    meta = {"fetched": time.strftime("%Y-%m-%d"), "cta_rows": len(cta), "narn_rows": len(feats),
            "metra_routes": len({f["properties"]["route"] for f in metra["features"]}),
            "cta_dataset": CTA_DATASET, "narn_url": NARN_URL, "metra_gtfs": METRA_GTFS_URL}
    for name, body in ((CTA_FILE, cta), (NARN_FILE, {"type": "FeatureCollection", "features": feats}),
                       (METRA_FILE, metra), (META_FILE, meta)):
        tmp = out / f".{name}.part"
        tmp.write_text(json.dumps(body))
        tmp.replace(out / name)
    return meta


def metra_from_gtfs(zip_bytes: bytes) -> dict:
    """Metra's route shapes, one feature per shape with its route id, name and color (Metra's GTFS feed; the map draws
    each line in Metra's own color, as Google Maps' transit layer does). Measured against the federal network: a
    median 9.5 ft apart inside the City, 98.3% within 50 ft. Only the three text tables are read."""
    import csv
    import io
    import zipfile

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    def table(name: str) -> list[dict]:
        text = zf.read(name).decode("utf-8-sig")
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]

    routes = {r["route_id"]: r for r in table("routes.txt")}
    shape_route = {t["shape_id"]: t["route_id"] for t in table("trips.txt") if t.get("shape_id")}
    pts: dict[str, list[tuple[int, float, float]]] = {}
    for r in table("shapes.txt"):
        if r["shape_id"] in shape_route:
            pts.setdefault(r["shape_id"], []).append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]),
                                                      float(r["shape_pt_lat"])))
    feats = []
    for sid, v in pts.items():
        if len(v) < 2:
            continue
        rid = shape_route[sid]
        rt = routes.get(rid, {})
        feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[x, y] for _, x, y in sorted(v)]},
                      "properties": {"route": rid, "name": rt.get("route_long_name") or rid,
                                     "color": "#" + (rt.get("route_color") or "005DAA").lstrip("#")}})
    if len({f["properties"]["route"] for f in feats}) < MIN_METRA_ROUTES:
        raise RuntimeError(f"Metra GTFS: only {len(feats)} shapes")
    return {"type": "FeatureCollection", "features": feats}


def cta_lines_of(text: str | None) -> list[str]:
    """'Brown, Orange, Pink, Purple (Exp)' → ['BR', 'OR', 'PK', 'PR'], in side-by-side order."""
    t = (text or "").lower()
    return [code for word, code in CTA_LINES if word.lower() in t]


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


def load(folder: Path, *, per_line: bool = False) -> list[tuple[str, object, dict]]:
    """Every drawn line: (kind, lon/lat geometry, props). Kinds: cta (elevated or at grade), cta_subway, metra,
    amtrak, freight, yard, spur. ``props`` has ``name`` and ``line`` (the City's legend code) for CTA lines.

    ``per_line`` (the map): a CTA segment several lines share becomes one feature per line with ``o``, its place
    side by side (-1.5, -0.5, 0.5, 1.5 for four), so the Loop draws every color next to each other as Google Maps does;
    and Metra comes from Metra's own feed (``metra_lines.geojson``, the line's color in ``color``) instead of the
    federal network's commuter segments, when that copy is there. The lot measurement keeps one feature per track."""
    out: list[tuple[str, object, dict]] = []
    for r in json.loads((folder / CTA_FILE).read_text()):
        if not r.get("the_geom"):
            continue
        sub = (r.get("type") or "").lower().startswith("subway")
        kind = "cta_subway" if sub else "cta"
        g = shape(r["the_geom"])
        legend = (r.get("legend") or "").strip().upper()
        codes = cta_lines_of(r.get("lines")) if per_line else []
        if len(codes) > 1:
            n = len(codes)
            for i, code in enumerate(codes):
                out.append((kind, g, {"name": cta_name(r.get("lines")), "line": code, "o": str(i - (n - 1) / 2)}))
        else:
            out.append((kind, g, {"name": cta_name(r.get("lines")), "line": codes[0] if codes else legend}))
    metra_own = per_line and (folder / METRA_FILE).exists()
    for f in json.loads((folder / NARN_FILE).read_text())["features"]:
        kind = narn_kind(f.get("properties") or {})
        if kind == "metra" and metra_own:
            continue
        if kind and f.get("geometry"):
            out.append((kind, shape(f["geometry"]), {}))
    if metra_own:
        for f in json.loads((folder / METRA_FILE).read_text())["features"]:
            p = f["properties"]
            out.append(("metra", shape(f["geometry"]), {"name": p.get("name") or "", "line": p.get("route") or "",
                                                        "color": p.get("color") or ""}))
    return out


SNAP_MAX_FT = 45.0  # move a stretch of L line onto CMAP's rail right-of-way only when it lies this close
SNAP_INSET_FT = 12.0  # how far inside the right-of-way a moved point lands
SNAP_STEP_FT = 15.0


def snap_to_row(line, row_ft: list, tree=None):
    """The L line moved onto CMAP's rail right-of-way where the City's "approximate" drawing runs beside it (the owner's
    map reviews: through the back yards at Dakin and Seminary, south of the Sheridan station). Works in feet
    (``to_feet``): points every 15 ft; a point already on rail land stays; one within 45 ft of it moves 12 ft inside;
    farther (the Loop's L over streets) stays. ``line`` and the result are lon/lat."""
    from shapely.ops import nearest_points

    if tree is None:
        tree = STRtree(np.array(row_ft, dtype=object))
    g = to_feet(line)
    out_parts = []
    for part in shapely.get_parts(g):
        n = max(2, int(part.length // SNAP_STEP_FT) + 1)
        pts = [part.interpolate(i * part.length / (n - 1)) for i in range(n)]
        moved = []
        for i, p in enumerate(pts):
            hit = tree.query(p, predicate="within")
            if len(hit):
                moved.append((p.x, p.y))
                continue
            near = tree.query_nearest(p, max_distance=SNAP_MAX_FT)
            if not len(near):
                moved.append((p.x, p.y))
                continue
            poly = row_ft[int(near[0])]
            b = nearest_points(poly.boundary, p)[0]
            dx, dy = b.x - p.x, b.y - p.y
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            # Only sideways: where the right-of-way lies ahead or behind along the line (a street the L crosses, which
            # CMAP doesn't map as rail), the point stays; moving it made a jog at Clark Junction (owner's look).
            a_, b_ = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
            tx, ty = b_.x - a_.x, b_.y - a_.y
            tl = (tx * tx + ty * ty) ** 0.5 or 1.0
            if abs(dx * tx + dy * ty) / (d * tl) > 0.5:
                moved.append((p.x, p.y))
                continue
            q = shapely.Point(b.x + dx / d * SNAP_INSET_FT, b.y + dy / d * SNAP_INSET_FT)
            moved.append((q.x, q.y) if poly.contains(q) else (b.x, b.y))
        # A moving average over 5 points (75 ft) takes out the zigzag where moved and kept stretches meet (owner's look);
        # the ends stay where they were, so segments still join.
        xy = np.array(moved)
        if len(xy) >= 5:
            k = np.ones(5) / 5
            sm = np.column_stack([np.convolve(np.pad(xy[:, i], 2, mode="edge"), k, mode="valid") for i in (0, 1)])
            sm[0], sm[-1] = xy[0], xy[-1]
            xy = sm
        out_parts.append(shapely.LineString(xy).simplify(3.0))
    merged = out_parts[0] if len(out_parts) == 1 else shapely.MultiLineString(out_parts)
    return shapely.transform(merged, lambda xy: np.column_stack([xy[:, 0] / _FT_PER_DEG_LON - 87.65,
                                                                 xy[:, 1] / _FT_PER_DEG_LAT + _LAT0]))


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
