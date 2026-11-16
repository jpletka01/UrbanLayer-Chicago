"""The new UI's base map, cut from the City of Chicago's own data (decision Item 90).

Layers (zooms 10-16; the map overzooms past 16):
- ``city``: the City boundary (``qqq8-j68g``), drawn as land; outside it the map shows only its background.
- ``water``: Lake Michigan, the rivers and lakes (``knfe-65pw``).
- ``park``: Chicago Park District parks (``ejsh-fztr``), from zoom 11.
- ``road``: street centerlines (``pr57-gg9e``) as ``kind`` highway / major / minor / local / ramp with a
  ``name`` for labels. Class 1 (expressways and Lake Shore Drive) and 2 (arterials) from zoom 10, 3 and ramps
  from 12, local streets from 13. Lower-level streets (class 7), river lines, runways and proposed, vacated
  or closed segments are left out.
- ``rail`` (decision Item 128): the CTA's L lines (City ``xbyr-jnvx``, elevated or at grade; the subway is not drawn) and
  the federal rail network (FRA/BTS NARN: Metra, Amtrak, freight, yards and spurs), cut to the City boundary, as
  ``kind`` cta / metra / amtrak / freight / yard / spur with a ``name`` on the L ("Brown Line"). Lines from zoom 10,
  yards from 13, spurs from 14. Read by ``rail_lines`` into the same folder. The L carries ``line``, the City's legend
  code, for its color.
- ``rail_land`` (Item 128, the owner's map review): CMAP 2023's rail right-of-way and intermodal yards (1511, 1570) as
  areas, from zoom 12, so rail land reads even where the County has no lot (the Kimball yard, the L north of
  Division are right-of-way without a PIN). From ``map_sources/cmap_lui_2023.db``; without it the layer is left out.
- ``park`` also carries CMAP 2023's cemeteries (1360), since their lots are not drawn (the owner's map review).
- ``station``: CTA rail and Metra stations (the committed ``ingestion/data/transit_stations.json``, from the CTA and
  Metra GTFS feeds) as points with ``kind`` cta / metra, ``name`` and ``lines``, from zoom 12.

The sources are read once per build and kept in ``backend/data/map_sources/`` so a rebuild can run offline::

    PYTHONPATH=. python -m backend.map_tiles.base_tiles [--offline] [--out <map_base.mbtiles>]
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date
from pathlib import Path

import httpx
from shapely.geometry import shape

from backend.map_tiles.tiler import Feature, to_mercator, write_mbtiles

log = logging.getLogger(__name__)

MIN_ZOOM, MAX_ZOOM = 10, 16
LAYERS = ["city", "water", "park", "rail_land", "rail", "station", "road"]

DATASETS = {
    "road": "pr57-gg9e",
    "water": "knfe-65pw",
    "park": "ejsh-fztr",
    "city": "qqq8-j68g",
}
SELECT = {
    "road": "the_geom,class,status,pre_dir,street_nam,street_typ",
    "water": "the_geom,name,display",
    "park": "the_geom,park,label",
    "city": "the_geom",
}

# City centerline class → (kind, first zoom). Anything not listed is left out.
ROAD_CLASSES: dict[str, tuple[str, int]] = {
    "1": ("highway", 10),
    "2": ("major", 10),
    "3": ("minor", 12),
    "9": ("ramp", 12),
    "4": ("local", 13),
    "5": ("local", 13),
    "E": ("local", 13),
    "S": ("local", 13),
}
# N = in use, UC = under construction, blank = unstated. P (proposed), V (vacated), C (closed) are left out.
ROAD_STATUS_KEPT = {"N", "UC", ""}

_TYPES = {
    "AVE": "Ave", "ST": "St", "BLVD": "Blvd", "DR": "Dr", "RD": "Rd", "PL": "Pl", "CT": "Ct", "PKWY": "Pkwy",
    "EXPY": "Expy", "TER": "Ter", "HWY": "Hwy", "LN": "Ln", "WAY": "Way", "SQ": "Sq", "PLZ": "Plz", "CIR": "Cir",
}


def is_island(row: dict) -> bool:
    """The City's hydro layer codes islands as ``display`` 2 (28 polygons, 43 acres, 95% inside parks, every one in a
    lagoon: Wooded Island, Humboldt Park's island); drawn as water they covered the land (owner's map review, Item 128).
    0 = water, 1 = narrow river edges, 4 = Lake Michigan."""
    return str(row.get("display") or "").strip() == "2"


def street_name(pre_dir: str | None, name: str | None, typ: str | None) -> str:
    """'N', 'MILWAUKEE', 'AVE' → 'N Milwaukee Ave'; ramps and unnamed segments → ''."""
    if not name:
        return ""
    words = []
    for w in name.split():
        words.append(w if any(ch.isdigit() for ch in w) and not w.isalpha() else w.capitalize())
    parts = [pre_dir.strip()] if pre_dir and pre_dir.strip() else []
    parts.append(" ".join(words))
    if typ and typ.strip():
        parts.append(_TYPES.get(typ.strip().upper(), typ.strip().capitalize()))
    return " ".join(parts)


def _fetch(dataset: str, select: str, *, token: str = "", page: int = 50_000) -> list[dict]:
    rows: list[dict] = []
    headers = {"X-App-Token": token} if token else {}
    with httpx.Client(timeout=120, headers=headers) as client:
        offset = 0
        while True:
            r = client.get(
                f"https://data.cityofchicago.org/resource/{dataset}.json",
                params={"$select": select, "$limit": page, "$offset": offset, "$order": ":id"},
            )
            r.raise_for_status()
            batch = r.json()
            rows += batch
            if len(batch) < page:
                return rows
            offset += page


def load_sources(cache_dir: Path, *, offline: bool) -> dict[str, list[dict]]:
    """Every source's rows, from the City portal (and saved to ``cache_dir``) or, offline, from ``cache_dir``.
    An empty or failed source raises: the base is never built from a partial read."""
    from backend.config import get_settings

    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, list[dict]] = {}
    for layer, dataset in DATASETS.items():
        path = cache_dir / f"{dataset}.json"
        if offline:
            rows = json.loads(path.read_text())
        else:
            rows = _fetch(dataset, SELECT[layer], token=get_settings().socrata_app_token)
            path.write_text(json.dumps(rows))
        if not rows:
            raise RuntimeError(f"{dataset} returned no rows: refusing to build the base without {layer}")
        out[layer] = rows
    return out


RAIL_MINZOOM = {"cta": MIN_ZOOM, "cta_subway": MIN_ZOOM, "metra": MIN_ZOOM, "amtrak": MIN_ZOOM, "freight": MIN_ZOOM,
                "yard": 13, "spur": 14}


def rail_features(lines: list[tuple[str, object, dict]], city) -> tuple[list[Feature], int]:
    """The drawn rail lines inside the City (``city`` = its boundary, lon/lat), and how many fell wholly outside."""
    from shapely.prepared import prep

    inside = prep(city)
    feats, outside = [], 0
    for kind, g, props in lines:
        if kind not in RAIL_MINZOOM:
            continue
        if not inside.intersects(g):
            outside += 1
            continue
        part = g if inside.contains(g) else g.intersection(city)
        if part.is_empty or part.length == 0:
            outside += 1
            continue
        feats.append(Feature("rail", to_mercator(part),
                             {"kind": kind, "name": props.get("name") or "", "line": props.get("line") or "",
                              "o": props.get("o") or "0", "color": props.get("color") or ""},
                             RAIL_MINZOOM[kind]))
    return feats, outside


RAIL_LAND_MINZOOM = STATION_MINZOOM = 12


def snap_l_lines(rail: list, cmap: Path) -> list:
    """The elevated / at-grade L moved onto CMAP's rail right-of-way where the City's approximate line runs beside it
    (``rail_lines.snap_to_row``; measured on the local copy: elevated L on rail land 46.8% -> 51.5%, built homes the
    line crosses for 25 ft or more 21 -> 5). The subway, Metra and freight are left as they are."""
    import sqlite3

    import numpy as np
    from shapely import from_wkb, make_valid
    from shapely.strtree import STRtree

    from backend.discovery.cmap_land_use import CMAP_INTERMODAL, CMAP_RAIL
    from backend.map_tiles import rail_lines

    db = sqlite3.connect(f"file:{cmap}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT wkb FROM lui WHERE landuse IN (?, ?)", (CMAP_RAIL, CMAP_INTERMODAL)).fetchall()
    finally:
        db.close()
    polys = []
    for (wkb,) in rows:
        g = from_wkb(wkb)
        polys.append(rail_lines.to_feet(g if g.is_valid else make_valid(g)))
    tree = STRtree(np.array(polys, dtype=object))
    cache: dict[int, object] = {}  # one CTA segment can arrive as several per-line features: snap it once
    out = []
    for kind, g, props in rail:
        if kind == "cta":
            key = id(g)
            if key not in cache:
                cache[key] = rail_lines.snap_to_row(g, polys, tree)
            g = cache[key]
        out.append((kind, g, props))
    return out


def cemetery_features(cmap: Path, city) -> list[Feature]:
    """CMAP 2023's cemeteries (1360) inside the City, drawn in the ``park`` layer (owner's map review: cemeteries read
    as parkland, and their lots are not drawn, so the base map must show them: Graceland, Rosehill, Oak Woods...)."""
    import sqlite3

    from shapely import from_wkb, make_valid
    from shapely.prepared import prep

    from backend.discovery.cmap_land_use import CMAP_CEMETERY

    db = sqlite3.connect(f"file:{cmap}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT wkb FROM lui WHERE landuse = ?", (CMAP_CEMETERY,)).fetchall()
    finally:
        db.close()
    inside = prep(city)
    out = []
    for (wkb,) in rows:
        g = from_wkb(wkb)
        g = g if g.is_valid else make_valid(g)
        if not inside.intersects(g):
            continue
        part = g if inside.contains(g) else g.intersection(city)
        if not part.is_empty and part.area > 0:
            out.append(Feature("park", to_mercator(part), {"name": ""}, 11))
    return out


def rail_land_features(cmap: Path, city) -> list[Feature]:
    """CMAP's rail right-of-way and intermodal yards inside the City, as areas."""
    import sqlite3

    from backend.discovery.cmap_land_use import CMAP_INTERMODAL, CMAP_RAIL

    db = sqlite3.connect(f"file:{cmap}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT landuse, wkb FROM lui WHERE landuse IN (?, ?)", (CMAP_RAIL, CMAP_INTERMODAL)).fetchall()
    finally:
        db.close()
    from shapely import from_wkb, make_valid
    from shapely.prepared import prep

    inside = prep(city)
    out = []
    for code, wkb in rows:
        g = from_wkb(wkb)
        g = g if g.is_valid else make_valid(g)
        if not inside.intersects(g):
            continue
        part = g if inside.contains(g) else g.intersection(city)
        if part.is_empty or part.area == 0:
            continue
        out.append(Feature("rail_land", to_mercator(part), {"kind": "yard" if code == CMAP_INTERMODAL else "row"},
                           RAIL_LAND_MINZOOM))
    return out


def station_features(stations: list[dict], city=None) -> list[Feature]:
    """Stations inside the City only (187 of 384 are in the suburbs: South Boulevard, Dempster, Oak Park...)."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    inside = prep(city) if city is not None else None
    out = []
    for s in stations:
        if s.get("lat") is None or s.get("lon") is None:
            continue
        if inside is not None and not inside.contains(Point(s["lon"], s["lat"])):
            continue
        kind = "cta" if s.get("type") == "cta_rail" else "metra" if s.get("type") == "metra" else None
        if kind:
            out.append(Feature("station", to_mercator(Point(s["lon"], s["lat"])),
                               {"kind": kind, "name": s.get("name") or "", "lines": ", ".join(s.get("lines") or [])},
                               STATION_MINZOOM))
    return out


def build_features(sources: dict[str, list[dict]], rail: list | None = None) -> tuple[list[Feature], dict[str, int]]:
    """Source rows → tile features, and what was left out by reason."""
    feats: list[Feature] = []
    left_out: dict[str, int] = {"road_class": 0, "road_status": 0, "no_geometry": 0}
    if rail is not None:
        from shapely.ops import unary_union

        city = unary_union([shape(r["the_geom"]) for r in sources["city"] if r.get("the_geom")])
        rail_feats, left_out["rail_outside_city"] = rail_features(rail, city)
        feats += rail_feats
        if sources.get("_cmap"):
            feats += rail_land_features(sources["_cmap"], city)
            feats += cemetery_features(sources["_cmap"], city)
        if sources.get("_stations"):
            feats += station_features(sources["_stations"], city)
    for row in sources["city"]:
        if row.get("the_geom"):
            feats.append(Feature("city", to_mercator(shape(row["the_geom"])), {}, MIN_ZOOM))
    left_out["water_islands"] = 0
    for row in sources["water"]:
        if not row.get("the_geom"):
            left_out["no_geometry"] += 1
            continue
        if is_island(row):
            left_out["water_islands"] += 1
            continue
        feats.append(Feature("water", to_mercator(shape(row["the_geom"])), {"name": (row.get("name") or "").title()},
                             MIN_ZOOM))
    for row in sources["park"]:
        if not row.get("the_geom"):
            left_out["no_geometry"] += 1
            continue
        feats.append(Feature("park", to_mercator(shape(row["the_geom"])),
                             {"name": row.get("label") or (row.get("park") or "").title()}, 11))
    for row in sources["road"]:
        cls = (row.get("class") or "").strip()
        if cls not in ROAD_CLASSES:
            left_out["road_class"] += 1
            continue
        if (row.get("status") or "").strip() not in ROAD_STATUS_KEPT:
            left_out["road_status"] += 1
            continue
        if not row.get("the_geom"):
            left_out["no_geometry"] += 1
            continue
        kind, minzoom = ROAD_CLASSES[cls]
        name = "" if kind == "ramp" else street_name(row.get("pre_dir"), row.get("street_nam"), row.get("street_typ"))
        feats.append(Feature("road", to_mercator(shape(row["the_geom"])), {"kind": kind, "name": name}, minzoom))
    return feats, left_out


def build_file(out: Path, *, offline: bool = False, minzoom: int = MIN_ZOOM, maxzoom: int = MAX_ZOOM) -> dict:
    t0 = time.monotonic()
    from backend.config import get_settings
    from backend.map_tiles import rail_lines

    cache = out.parent / "map_sources"
    sources = load_sources(cache, offline=offline)
    if not offline:
        rail_lines.fetch(cache, token=get_settings().socrata_app_token)
    elif not rail_lines.present(cache):
        raise RuntimeError(f"no rail lines in {cache}: run python -m backend.map_tiles.rail_lines first")
    cmap = cache / "cmap_lui_2023.db"
    if cmap.exists() and cmap.stat().st_size:
        sources["_cmap"] = cmap
    else:
        log.warning("base tiles: %s missing; the rail_land layer is left out", cmap)
    stations = get_settings().data_dir / "transit_stations.json"
    sources["_stations"] = json.loads(stations.read_text()) if stations.exists() else []
    if not sources["_stations"]:
        log.warning("base tiles: no transit stations at %s; the station layer is left out", stations)
    rail = rail_lines.load(cache, per_line=True)
    if sources.get("_cmap"):
        rail = snap_l_lines(rail, sources["_cmap"])
    feats, left_out = build_features(sources, rail)
    counts = {k: sum(1 for f in feats if f.layer == k) for k in LAYERS}
    stats = write_mbtiles(
        out, feats, name="map_base", minzoom=minzoom, maxzoom=maxzoom, layer_order=LAYERS,
        fields={"city": {}, "water": {"name": "String"}, "park": {"name": "String"},
                "road": {"kind": "String", "name": "String"}, "rail": {"kind": "String", "name": "String", "line": "String", "o": "String", "color": "String"},
                "rail_land": {"kind": "String"}, "station": {"kind": "String", "name": "String", "lines": "String"}},
        extra_meta={"built_at": date.today().isoformat(), "counts": json.dumps(counts),
                    "left_out": json.dumps(left_out),
                    "sources": json.dumps(DATASETS | {"rail": "xbyr-jnvx + FRA/BTS NARN"})},
        log=log,
    )
    summary = {
        "counts": counts, "left_out": left_out, "tiles": stats.tiles,
        "mb_gz": {z: round(b / 1e6, 2) for z, b in stats.bytes_gz.items()},
        "max_tile_kb_gz": {z: round(b / 1e3, 1) for z, b in stats.max_tile_gz.items()},
        "pieces_unclipped": sum(stats.unclipped.values()),
        "seconds": round(time.monotonic() - t0, 1), "file_mb": round(out.stat().st_size / 1e6, 2),
    }
    log.info("map base tiles: %s", json.dumps(summary))
    return summary


def main() -> None:
    from backend.config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="default: settings.map_base_tiles_path")
    ap.add_argument("--offline", action="store_true", help="rebuild from backend/data/map_sources/ only")
    ap.add_argument("--minzoom", type=int, default=MIN_ZOOM)
    ap.add_argument("--maxzoom", type=int, default=MAX_ZOOM)
    args = ap.parse_args()
    out = args.out or get_settings().map_base_tiles_path
    print(json.dumps(build_file(out, offline=args.offline, minzoom=args.minzoom, maxzoom=args.maxzoom), indent=1))


if __name__ == "__main__":
    main()
