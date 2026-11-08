"""Official zoning as the new UI's own map tiles (map track M3, decision Items 90+).

Source: the City's Zoning MapServer layer 1 (the same layer the Profile's point lookup reads), every district
with its source attributes (zone class and type, ordinance number and date, case number, PD number, PMD
sub-area, Clerk document number, zoning id). Staff user ids are not copied.

Geometry: the source polygons, unsimplified at every zoom (13-16; the map overzooms past 16), quantized only
to the tile grid (about 0.9 m at zoom 13, 0.1 m at 16). Neighbors keep their shared edges, so no slivers open
between them (per-feature simplification caused the 2026-10-20 slivers, research/15 §1.2), and no lot's
district can move. Shared-edge simplification (shapely ``coverage_simplify``) was tried and refused: the
City's layer is not a valid coverage (``coverage_is_valid`` is false over its 15,043 districts), so its
output can't be trusted; the cost is payload (largest tile 93 KB at zoom 13, 8.8 KB at 16; decision Item 91).
Streets stay visible because the map draws its roads above zoning, never by clipping zoning to blocks.

Layer ``zoning_label`` holds one point per district part (polylabel, the part's visual center), from a zoom
that depends on its size, for the district-code labels.

    PYTHONPATH=. python -m backend.map_tiles.zoning_tiles [--offline] [--out <map_zoning.mbtiles>]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import shapely
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import polylabel

from backend.map_tiles.tiler import Feature, mercator_meters_per_unit, to_mercator, write_mbtiles

log = logging.getLogger(__name__)

LAYER_URL = "https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer/1/query"
OUT_FIELDS = ("OBJECTID,ZONING_ID,CASE_NUMBER,ZONE_TYPE,ZONE_CLASS,ORDINANCE_NUM,ORDINANCE_DATE,PD_NUM,"
              "PMD_SUB_AREA,CLERK_DOCNO")
MIN_ZOOM, MAX_ZOOM = 13, 16
LAYERS = ["zoning", "zoning_label"]
PAGE = 2000

_DOWNTOWN = re.compile(r"^D[CXRS]")


def family(zone_class: str) -> str:
    """The district family the map colors by: residential, business, manufacturing, downtown, planned,
    park, transport, other."""
    z = (zone_class or "").upper().strip()
    if z.startswith("PMD"):
        return "manufacturing"
    if z.startswith("POS"):
        return "park"
    if z.startswith("PD"):
        return "planned"
    if z.startswith(("RS", "RT", "RM")):
        return "residential"
    if _DOWNTOWN.match(z):
        return "downtown"
    if z.startswith(("B", "C")):
        return "business"
    if z.startswith("M"):
        return "manufacturing"
    if z.startswith("T"):
        return "transport"
    return "other"


def level(zone_class: str) -> str:
    """Intensity step 1-4 inside a family (the map darkens the family's color as it rises), from the district's
    own name: RS 1, RT 2, RM-4.5/5 3, RM-6 and up 4; B/C/M/D by the number after the dash (1-2 → 1, 3 → 2,
    5 → 3, 6 and up → 4). Planned, park, transport and other are '1'."""
    z = (zone_class or "").upper().strip()
    fam = family(z)
    if fam == "residential":
        if z.startswith("RS"):
            return "1"
        if z.startswith("RT"):
            return "2"
        m = re.search(r"-(\d+(?:\.\d+)?)", z)
        return "4" if m and float(m.group(1)) >= 6 else "3"
    if fam in ("business", "manufacturing", "downtown") and not z.startswith("PMD"):
        m = re.search(r"-(\d+(?:\.\d+)?)", z)
        if not m:
            return "1"
        v = float(m.group(1))
        return "1" if v <= 2 else "2" if v <= 3 else "3" if v <= 5 else "4"
    return "1"


def _fetch_all() -> list[dict]:
    feats: list[dict] = []
    with httpx.Client(timeout=120) as client:
        offset = 0
        while True:
            r = client.get(LAYER_URL, params={
                "where": "1=1", "outFields": OUT_FIELDS, "outSR": 4326, "f": "geojson",
                "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": PAGE,
            })
            r.raise_for_status()
            body = r.json()
            if "features" not in body:  # ArcGIS answers a failed query with 200 and an error body (Item 65)
                raise RuntimeError(f"zoning layer query failed at offset {offset}: {str(body)[:200]}")
            batch = body["features"]
            feats += batch
            if len(batch) < PAGE:
                return feats
            offset += PAGE


def load_source(cache_dir: Path, *, offline: bool) -> list[dict]:
    """Every district as GeoJSON features (and saved to ``cache_dir``), or offline from ``cache_dir``. An empty
    read raises: the tiles are never built from a partial layer."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "zoning_layer1.geojson"
    if offline:
        feats = json.loads(path.read_text())["features"]
    else:
        feats = _fetch_all()
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    if len(feats) < 10_000:
        raise RuntimeError(f"zoning layer returned {len(feats)} districts (expected ~15,000): refusing to build")
    return feats


def _iso(ms) -> str:
    if ms in (None, ""):
        return ""
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).date().isoformat()


def source_props(p: dict) -> dict[str, str]:
    """The tile properties: the source attributes as strings, plus the family and level the style reads."""
    zc = (p.get("ZONE_CLASS") or "").strip()
    out = {
        "zone_class": zc,
        "family": family(zc),
        "level": level(zc),
        "zone_type": "" if p.get("ZONE_TYPE") is None else str(p["ZONE_TYPE"]),
        "zoning_id": "" if p.get("ZONING_ID") is None else str(p["ZONING_ID"]),
        "ordinance_num": (p.get("ORDINANCE_NUM") or "").strip(),
        "ordinance_date": _iso(p.get("ORDINANCE_DATE")),
        "case_number": "" if p.get("CASE_NUMBER") is None else str(p["CASE_NUMBER"]),
        "pd_num": "" if p.get("PD_NUM") is None else str(p["PD_NUM"]),
        "pmd_sub_area": (p.get("PMD_SUB_AREA") or "").strip(),
        "clerk_docno": (p.get("CLERK_DOCNO") or "").strip(),
    }
    return {k: v for k, v in out.items() if v != ""}


def _polygonal(g):
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    parts = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    return MultiPolygon(parts) if parts else None


def label_minzoom(area_m2: float) -> int:
    """Bigger districts are labeled earlier: 13 from 200,000 m², 14 from 40,000, 15 from 8,000, else 16."""
    return 13 if area_m2 >= 200_000 else 14 if area_m2 >= 40_000 else 15 if area_m2 >= 8_000 else 16


def build_features(source: list[dict]) -> tuple[list[Feature], dict]:
    geoms: list = []
    props: list[dict[str, str]] = []
    report = {"districts": 0, "no_geometry": 0, "repaired": 0, "coverage_valid": None}
    for f in source:
        if not f.get("geometry"):
            report["no_geometry"] += 1
            continue
        g = shape(f["geometry"])
        if not g.is_valid:
            g = _polygonal(shapely.make_valid(g))
            report["repaired"] += 1
            if g is None:
                report["no_geometry"] += 1
                continue
        geoms.append(to_mercator(g))
        props.append(source_props(f.get("properties") or {}))
    report["districts"] = len(geoms)

    # Recorded for the build report; the tiles never use a simplified shape (see the module docstring).
    report["coverage_valid"] = bool(shapely.coverage_is_valid(geoms))

    feats: list[Feature] = []
    meters = mercator_meters_per_unit(41.85)
    for g, p in zip(geoms, props):
        feats.append(Feature("zoning", g, p, MIN_ZOOM, simplify=False))
        parts = g.geoms if isinstance(g, MultiPolygon) else [g]
        for part in parts:
            if not isinstance(part, Polygon) or part.is_empty:
                continue
            area_m2 = part.area * meters * meters
            try:
                pt = polylabel(part, tolerance=part.length / 2000 or 1e-9)
            except Exception:  # noqa: BLE001 - a degenerate part falls back to an interior point
                pt = part.representative_point()
            lp = {"zone_class": p.get("zone_class", ""), "family": p.get("family", "other")}
            feats.append(Feature("zoning_label", pt, lp, max(MIN_ZOOM, label_minzoom(area_m2)), simplify=False))
    return feats, report


def build_file(out: Path, *, offline: bool = False) -> dict:
    t0 = time.monotonic()
    source = load_source(out.parent / "map_sources", offline=offline)
    feats, report = build_features(source)
    stats = write_mbtiles(
        out, feats, name="map_zoning", minzoom=MIN_ZOOM, maxzoom=MAX_ZOOM, layer_order=LAYERS,
        fields={"zoning": {k: "String" for k in ("zone_class", "family", "level", "zone_type", "zoning_id",
                                                  "ordinance_num", "ordinance_date", "case_number", "pd_num",
                                                  "pmd_sub_area", "clerk_docno")},
                "zoning_label": {"zone_class": "String", "family": "String"}},
        extra_meta={"built_at": date.today().isoformat(), "source": LAYER_URL, "report": json.dumps(report)},
        log=log,
    )
    summary = {
        **report, "tiles": stats.tiles,
        "mb_gz": {z: round(b / 1e6, 2) for z, b in stats.bytes_gz.items()},
        "max_tile_kb_gz": {z: round(b / 1e3, 1) for z, b in stats.max_tile_gz.items()},
        "pieces_unclipped": sum(stats.unclipped.values()),
        "seconds": round(time.monotonic() - t0, 1), "file_mb": round(out.stat().st_size / 1e6, 2),
    }
    log.info("map zoning tiles: %s", json.dumps(summary))
    return summary


def main() -> None:
    from backend.config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="default: settings.map_zoning_tiles_path")
    ap.add_argument("--offline", action="store_true", help="rebuild from backend/data/map_sources/ only")
    args = ap.parse_args()
    out = args.out or get_settings().map_zoning_tiles_path
    print(json.dumps(build_file(out, offline=args.offline), indent=1))


if __name__ == "__main__":
    main()
