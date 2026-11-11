"""Chicago's 98 named neighborhoods for Discovery (owner's call, 2026-11-10; decision Item 104).

The index already knows the 77 community areas; people search by neighborhood ("Wicker Park" is inside West Town).
The City publishes neighborhood boundaries (``y6yq-dbs2``, "Boundaries - Neighborhoods": 98 areas, last updated 2012,
the names Chicagoans use). A copy simplified to about 5 m is committed beside this file (``neighborhoods.geojson``,
built by ``python -m backend.discovery.neighborhoods``); the index build tags every lot with the neighborhood its point
falls in (``attrs["hood"]``), and a search region ``hood:<slug>`` matches it (``parcel_index``). Nothing here runs on
a request except the name lookups.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import shapely
from shapely.geometry import mapping, shape
from shapely.strtree import STRtree

DATASET = "y6yq-dbs2"
PATH = Path(__file__).with_name("neighborhoods.geojson")
PREFIX = "hood:"
MIN_AREAS = 90  # 98 published; fewer means a partial read


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def build(out: Path = PATH) -> dict:
    """Fetch the City's layer and write the simplified copy (run by hand; the copy is committed)."""
    import httpx

    rows = httpx.get(f"https://data.cityofchicago.org/resource/{DATASET}.json", params={"$limit": 500}, timeout=120).json()
    feats = []
    for r in rows:
        name = (r.get("pri_neigh") or "").strip()
        if not name or not r.get("the_geom"):
            continue
        g = shape(r["the_geom"])
        g = (g if g.is_valid else shapely.make_valid(g)).simplify(0.00005, preserve_topology=True)
        label = shapely.point_on_surface(g)
        feats.append({"type": "Feature", "properties": {"slug": slug(name), "name": name,
                                                        "lx": round(label.x, 5), "ly": round(label.y, 5)},
                      "geometry": json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 6))})
    if len(feats) < MIN_AREAS:
        raise RuntimeError(f"{DATASET} returned {len(feats)} neighborhoods: refusing to write")
    feats.sort(key=lambda f: f["properties"]["name"])
    out.write_text(json.dumps({"type": "FeatureCollection", "source": DATASET, "features": feats}, separators=(",", ":")))
    return {"neighborhoods": len(feats), "bytes": out.stat().st_size}


@lru_cache(maxsize=1)
def _load() -> tuple[list[dict], STRtree | None, list]:
    if not PATH.exists():
        return [], None, []
    fc = json.loads(PATH.read_text())
    props = [f["properties"] for f in fc["features"]]
    geoms = [shape(f["geometry"]) for f in fc["features"]]
    return props, STRtree(geoms) if geoms else None, geoms


def names() -> dict[str, str]:
    """slug -> name for every neighborhood."""
    return {p["slug"]: p["name"] for p in _load()[0]}


def neighborhood_of(lat: float | None, lon: float | None) -> str | None:
    """The slug of the neighborhood a point falls in, or None (outside every one, or no copy)."""
    props, tree, geoms = _load()
    if tree is None or lat is None or lon is None:
        return None
    pt = shapely.Point(lon, lat)
    for i in tree.query(pt, predicate="within"):
        return props[i]["slug"]
    return None


def geojson_bytes() -> bytes:
    return PATH.read_bytes() if PATH.exists() else b'{"type":"FeatureCollection","features":[]}'


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
