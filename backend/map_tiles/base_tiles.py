"""The new UI's base map, cut from the City of Chicago's own data (decision Item 90).

Layers (zooms 10-16; the map overzooms past 16):
- ``city``: the City boundary (``qqq8-j68g``), drawn as land; outside it the map shows only its background.
- ``water``: Lake Michigan, the rivers and lakes (``knfe-65pw``).
- ``park``: Chicago Park District parks (``ejsh-fztr``), from zoom 11.
- ``road``: street centerlines (``pr57-gg9e``) as ``kind`` highway / major / minor / local / ramp with a
  ``name`` for labels. Class 1 (expressways and Lake Shore Drive) and 2 (arterials) from zoom 10, 3 and ramps
  from 12, local streets from 13. Lower-level streets (class 7), river lines, runways and proposed, vacated
  or closed segments are left out.

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
LAYERS = ["city", "water", "park", "road"]

DATASETS = {
    "road": "pr57-gg9e",
    "water": "knfe-65pw",
    "park": "ejsh-fztr",
    "city": "qqq8-j68g",
}
SELECT = {
    "road": "the_geom,class,status,pre_dir,street_nam,street_typ",
    "water": "the_geom,name",
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


def build_features(sources: dict[str, list[dict]]) -> tuple[list[Feature], dict[str, int]]:
    """Source rows → tile features, and what was left out by reason."""
    feats: list[Feature] = []
    left_out: dict[str, int] = {"road_class": 0, "road_status": 0, "no_geometry": 0}
    for row in sources["city"]:
        if row.get("the_geom"):
            feats.append(Feature("city", to_mercator(shape(row["the_geom"])), {}, MIN_ZOOM))
    for row in sources["water"]:
        if not row.get("the_geom"):
            left_out["no_geometry"] += 1
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
    sources = load_sources(out.parent / "map_sources", offline=offline)
    feats, left_out = build_features(sources)
    counts = {k: sum(1 for f in feats if f.layer == k) for k in LAYERS}
    stats = write_mbtiles(
        out, feats, name="map_base", minzoom=minzoom, maxzoom=maxzoom, layer_order=LAYERS,
        fields={"city": {}, "water": {"name": "String"}, "park": {"name": "String"},
                "road": {"kind": "String", "name": "String"}},
        extra_meta={"built_at": date.today().isoformat(), "counts": json.dumps(counts),
                    "left_out": json.dumps(left_out),
                    "sources": json.dumps(DATASETS)},
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
